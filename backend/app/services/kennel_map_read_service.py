from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.demo_clock import DemoClock
from app.models import Dog, KennelLocation
from app.models.enums import AvailabilityState, LifecycleState, LocationType
from app.schemas.kennel_map import (
    KennelMapLocationRead,
    KennelMapResidentRead,
    KennelMapSnapshotRead,
    KennelMapSummaryRead,
)
from app.services.effective_state import EffectiveDogState


class KennelMapReadService:
    """Build one bounded-query, internally consistent historical kennel snapshot."""

    def __init__(self, session: Session, clock: DemoClock) -> None:
        self.session = session
        self.clock = clock

    def snapshot(self, on_date: date) -> KennelMapSnapshotRead:
        locations = list(
            self.session.scalars(
                select(KennelLocation).where(KennelLocation.is_active.is_(True))
            )
        )
        dogs = list(
            self.session.scalars(
                select(Dog).options(
                    selectinload(Dog.litter),
                    selectinload(Dog.class_periods),
                    selectinload(Dog.lifecycle_periods),
                    selectinload(Dog.availability_periods),
                    selectinload(Dog.housing_assignments),
                )
            ).unique()
        )
        locations_by_id = {location.id: location for location in locations}
        state = EffectiveDogState(on_date)
        residents_by_location: dict[int, list[KennelMapResidentRead]] = defaultdict(
            list
        )

        for dog in dogs:
            if dog.birth_date > on_date:
                continue
            lifecycle = state.lifecycle(dog)
            if lifecycle != LifecycleState.ACTIVE.value:
                continue
            housing = state.housing(dog)
            if housing is None:
                continue
            location = locations_by_id.get(housing.location_id)
            if location is None:
                continue
            dog_class, _ = state.dog_class(dog)
            residents_by_location[housing.location_id].append(
                KennelMapResidentRead(
                    id=dog.public_id,
                    name=dog.name,
                    sex=dog.sex,
                    is_neutered=dog.is_neutered,
                    dog_class=dog_class,
                    lifecycle=lifecycle,
                    availability=state.availability(dog),
                    housing_code=location.code,
                    litter_code=dog.litter.code if dog.litter else None,
                    photo_key=dog.photo_key,
                )
            )

        location_reads = [
            KennelMapLocationRead(
                id=location.code,
                code=location.code,
                display_name=location.display_name,
                location_type=location.location_type,
                zone=location.zone,
                row=location.row_label,
                position=location.position,
                capacity=location.capacity,
                is_active=location.is_active,
                residents=sorted(
                    residents_by_location[location.id], key=lambda dog: dog.name
                ),
            )
            for location in sorted(locations, key=self._location_order)
        ]
        residents = [
            resident for location in location_reads for resident in location.residents
        ]
        availability_counts = Counter(
            resident.availability or "unknown" for resident in residents
        )
        return KennelMapSnapshotRead(
            selected_date=on_date,
            season_start=self.clock.season_start,
            season_end=self.clock.season_end,
            reference_date=self.clock.reference_date,
            summary=KennelMapSummaryRead(
                resident_dogs=len(residents),
                occupied_locations=sum(
                    bool(location.residents) for location in location_reads
                ),
                unavailable_dogs=sum(
                    resident.availability != AvailabilityState.AVAILABLE.value
                    for resident in residents
                ),
                class_counts=dict(
                    sorted(
                        Counter(
                            resident.dog_class or "unknown" for resident in residents
                        ).items()
                    )
                ),
                sex_counts=dict(
                    sorted(Counter(resident.sex for resident in residents).items())
                ),
                neutered_counts={
                    "intact": sum(not resident.is_neutered for resident in residents),
                    "neutered": sum(resident.is_neutered for resident in residents),
                },
                availability_counts=dict(sorted(availability_counts.items())),
            ),
            locations=location_reads,
        )

    @staticmethod
    def _location_order(location: KennelLocation) -> tuple[int, str, str, int]:
        type_rank = (
            0 if location.location_type == LocationType.ADULT_ENCLOSURE.value else 1
        )
        return type_rank, location.zone, location.row_label, location.position
