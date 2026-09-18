from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.demo_clock import DemoClock
from app.domain.analytics import summarize_work_distances
from app.models import (
    Dog,
    HousingAssignment,
    KennelLocation,
    Litter,
    WorkParticipation,
    WorkSession,
)
from app.models.enums import LifecycleState
from app.schemas.dogs import (
    ActivePopulationSummaryRead,
    ArchiveListItemRead,
    ArchiveRead,
    ArchiveRegistryRead,
    ArchiveSort,
    CurrentDogStateRead,
    DogHistoryRead,
    DogListItemRead,
    DogPedigreeRead,
    DogProfileRead,
    DogSort,
    DogsRegistryRead,
    DogWeeklyWorkRead,
    DogWorkEntryRead,
    DogWorkRead,
    DogWorkSummaryRead,
    GrandparentPairRead,
    HousingHistoryRead,
    LitterPedigreeRead,
    LocationRead,
    OffspringLitterRead,
    PeriodHistoryRead,
    RelatedDogRead,
)
from app.services.demo_workspace_service import scoped_date_filter
from app.services.effective_state import EffectiveDogState, effective_period


def age_at(birth_date: date, reference_date: date) -> tuple[int, int, str]:
    total_months = (reference_date.year - birth_date.year) * 12
    total_months += reference_date.month - birth_date.month
    if reference_date.day < birth_date.day:
        total_months -= 1
    total_months = max(total_months, 0)
    years, months = divmod(total_months, 12)
    if years == 0:
        label = f"{months} month" if months == 1 else f"{months} months"
    elif months == 0:
        label = f"{years} year" if years == 1 else f"{years} years"
    else:
        year_word = "year" if years == 1 else "years"
        month_word = "month" if months == 1 else "months"
        label = f"{years} {year_word}, {months} {month_word}"
    return years, months, label


def location_read(location: KennelLocation) -> LocationRead:
    return LocationRead(
        code=location.code,
        display_name=location.display_name,
        location_type=location.location_type,
        zone=location.zone,
        row=location.row_label,
    )


class DogReadService:
    """Read-only P3 projections with one shared effective-state policy."""

    def __init__(
        self, session: Session, clock: DemoClock, workspace_id: int | None = None
    ) -> None:
        self.session = session
        self.clock = clock
        self.workspace_id = workspace_id
        self._dogs: list[Dog] | None = None
        self._pedigree_dogs: list[Dog] | None = None
        self._litters: list[Litter] | None = None

    def _all_dogs(self) -> list[Dog]:
        if self._dogs is None:
            self._dogs = list(
                self.session.scalars(
                    select(Dog).options(
                        selectinload(Dog.litter),
                        selectinload(Dog.class_periods),
                        selectinload(Dog.lifecycle_periods),
                        selectinload(Dog.availability_periods),
                        selectinload(Dog.archive),
                        selectinload(Dog.role_capabilities),
                        selectinload(Dog.housing_assignments).selectinload(
                            HousingAssignment.location
                        ),
                    )
                ).unique()
            )
        return self._dogs

    def _all_litters(self) -> list[Litter]:
        if self._litters is None:
            self._litters = list(self.session.scalars(select(Litter)))
        return self._litters

    def _dog(self, public_id: UUID) -> Dog | None:
        return self.session.scalar(
            select(Dog)
            .where(Dog.public_id == public_id)
            .options(
                selectinload(Dog.litter),
                selectinload(Dog.class_periods),
                selectinload(Dog.lifecycle_periods),
                selectinload(Dog.availability_periods),
                selectinload(Dog.archive),
                selectinload(Dog.role_capabilities),
                selectinload(Dog.housing_assignments).selectinload(
                    HousingAssignment.location
                ),
            )
        )

    def _all_pedigree_dogs(self) -> list[Dog]:
        if self._pedigree_dogs is None:
            self._pedigree_dogs = list(
                self.session.scalars(
                    select(Dog).options(
                        selectinload(Dog.litter),
                        selectinload(Dog.class_periods),
                        selectinload(Dog.lifecycle_periods),
                    )
                ).unique()
            )
        return self._pedigree_dogs

    def _lifecycle(self, dog: Dog) -> str:
        return EffectiveDogState(self.clock.reference_date).lifecycle(dog) or "unknown"

    def _class(self, dog: Dog) -> tuple[str | None, bool]:
        return EffectiveDogState(self.clock.reference_date).dog_class(
            dog, historical_fallback=True
        )

    def _availability(self, dog: Dog) -> str | None:
        return EffectiveDogState(self.clock.reference_date).availability(dog)

    def _current_housing_assignment(self, dog: Dog) -> HousingAssignment | None:
        return EffectiveDogState(self.clock.reference_date).housing(dog)

    def _last_housing_assignment(self, dog: Dog) -> HousingAssignment | None:
        return max(
            dog.housing_assignments,
            key=lambda row: (row.valid_to or date.max, row.valid_from),
            default=None,
        )

    def _state(self, dog: Dog) -> CurrentDogStateRead:
        dog_class, historical = self._class(dog)
        housing = self._current_housing_assignment(dog)
        return CurrentDogStateRead(
            reference_date=self.clock.reference_date,
            lifecycle=self._lifecycle(dog),
            dog_class=dog_class,
            class_is_historical=historical,
            availability=self._availability(dog),
            housing=location_read(housing.location) if housing else None,
        )

    def _archive(self, dog: Dog) -> ArchiveRead | None:
        if not dog.archive:
            return None
        return ArchiveRead(
            archive_date=dog.archive.archive_date,
            reason=dog.archive.reason,
            note=dog.archive.note,
        )

    def _list_item(self, dog: Dog) -> DogListItemRead:
        years, months, label = age_at(dog.birth_date, self.clock.reference_date)
        return DogListItemRead(
            id=dog.public_id,
            name=dog.name,
            birth_date=dog.birth_date,
            age_years=years,
            age_months=months,
            age_label=label,
            sex=dog.sex,
            is_neutered=dog.is_neutered,
            litter_code=dog.litter.code if dog.litter else None,
            capabilities=sorted(role.role for role in dog.role_capabilities),
            state=self._state(dog),
            photo_key=dog.photo_key,
        )

    def list_active(
        self,
        *,
        search: str | None,
        dog_class: str | None,
        sex: str | None,
        availability: str | None,
        neutered: bool | None,
        housing: str | None,
        capability: str | None,
        sort: DogSort,
    ) -> DogsRegistryRead:
        active = [
            self._list_item(dog)
            for dog in self._all_dogs()
            if self._lifecycle(dog) == LifecycleState.ACTIVE.value
        ]
        counts = Counter(item.state.dog_class for item in active)
        filtered = list(active)
        if search:
            needle = search.strip().casefold()
            filtered = [
                item
                for item in filtered
                if needle in item.name.casefold()
                or (
                    item.state.housing is not None
                    and needle in item.state.housing.code.casefold()
                )
            ]
        if dog_class:
            filtered = [item for item in filtered if item.state.dog_class == dog_class]
        if sex:
            filtered = [item for item in filtered if item.sex == sex]
        if availability:
            filtered = [
                item for item in filtered if item.state.availability == availability
            ]
        if neutered is not None:
            filtered = [item for item in filtered if item.is_neutered is neutered]
        if housing:
            housing_key = housing.strip().casefold()
            filtered = [
                item
                for item in filtered
                if item.state.housing is not None
                and housing_key
                in {
                    item.state.housing.code.casefold(),
                    item.state.housing.zone.casefold(),
                    (item.state.housing.zone + item.state.housing.row).casefold(),
                }
            ]
        if capability:
            filtered = [item for item in filtered if capability in item.capabilities]

        class_rank = {"puppy": 0, "junior": 1, "training": 2, "standard": 3}
        if sort == DogSort.YOUNGEST:
            filtered.sort(key=lambda item: (-item.birth_date.toordinal(), item.name))
        elif sort == DogSort.OLDEST:
            filtered.sort(key=lambda item: (item.birth_date, item.name))
        elif sort == DogSort.HOUSING:
            filtered.sort(
                key=lambda item: (
                    item.state.housing.code if item.state.housing else "ZZZ",
                    item.name,
                )
            )
        elif sort == DogSort.CLASS:
            filtered.sort(
                key=lambda item: (
                    class_rank.get(item.state.dog_class or "", 99),
                    item.name,
                )
            )
        else:
            filtered.sort(key=lambda item: item.name)

        groups = sorted(
            {
                item.state.housing.zone + item.state.housing.row
                for item in active
                if item.state.housing
                and item.state.housing.location_type == "adult_enclosure"
            }
            | {
                "PUPPY"
                for item in active
                if item.state.housing
                and item.state.housing.location_type == "puppy_area"
            }
        )
        return DogsRegistryRead(
            reference_date=self.clock.reference_date,
            result_count=len(filtered),
            summary=ActivePopulationSummaryRead(
                total=len(active),
                puppy=counts["puppy"],
                junior=counts["junior"],
                training=counts["training"],
                standard=counts["standard"],
            ),
            housing_groups=groups,
            items=filtered,
        )

    def list_archived(
        self,
        *,
        search: str | None,
        reason: str | None,
        sort: ArchiveSort,
    ) -> ArchiveRegistryRead:
        litters = self._all_litters()
        litter_sizes = Counter(
            dog.litter_id for dog in self._all_dogs() if dog.litter_id is not None
        )
        archived: list[ArchiveListItemRead] = []
        for dog in self._all_dogs():
            if self._lifecycle(dog) != LifecycleState.ARCHIVED.value or not dog.archive:
                continue
            years, months, label = age_at(dog.birth_date, self.clock.reference_date)
            archive = self._archive(dog)
            assert archive is not None
            archived.append(
                ArchiveListItemRead(
                    id=dog.public_id,
                    name=dog.name,
                    birth_date=dog.birth_date,
                    age_years=years,
                    age_months=months,
                    age_label=label,
                    sex=dog.sex,
                    litter_code=dog.litter.code if dog.litter else None,
                    archive=archive,
                    offspring_count=sum(
                        litter_sizes[litter.id]
                        for litter in litters
                        if litter.mother_id == dog.id or litter.father_id == dog.id
                    ),
                    photo_key=dog.photo_key,
                )
            )
        filtered = archived
        if search:
            needle = search.strip().casefold()
            filtered = [item for item in filtered if needle in item.name.casefold()]
        if reason:
            filtered = [item for item in filtered if item.archive.reason == reason]
        if sort == ArchiveSort.ARCHIVE_DATE_DESC:
            filtered.sort(
                key=lambda item: (item.archive.archive_date, item.name), reverse=True
            )
        elif sort == ArchiveSort.ARCHIVE_DATE_ASC:
            filtered.sort(key=lambda item: (item.archive.archive_date, item.name))
        elif sort == ArchiveSort.YOUNGEST:
            filtered.sort(key=lambda item: (-item.birth_date.toordinal(), item.name))
        elif sort == ArchiveSort.OLDEST:
            filtered.sort(key=lambda item: (item.birth_date, item.name))
        else:
            filtered.sort(key=lambda item: item.name)
        return ArchiveRegistryRead(
            reference_date=self.clock.reference_date,
            result_count=len(filtered),
            total_archived=len(archived),
            items=filtered,
        )

    def profile(self, public_id: UUID) -> DogProfileRead | None:
        dog = self._dog(public_id)
        if not dog:
            return None
        years, months, label = age_at(dog.birth_date, self.clock.reference_date)
        last_housing = self._last_housing_assignment(dog)
        return DogProfileRead(
            id=dog.public_id,
            name=dog.name,
            birth_date=dog.birth_date,
            age_years=years,
            age_months=months,
            age_label=label,
            sex=dog.sex,
            is_neutered=dog.is_neutered,
            neutered_on=dog.neutered_on,
            photo_key=dog.photo_key,
            notes=dog.notes,
            litter_code=dog.litter.code if dog.litter else None,
            litter_birth_date=dog.litter.birth_date if dog.litter else None,
            capabilities=sorted(role.role for role in dog.role_capabilities),
            state=self._state(dog),
            archive=self._archive(dog),
            last_known_housing=(
                location_read(last_housing.location) if last_housing else None
            ),
        )

    def _related(self, dog: Dog | None) -> RelatedDogRead | None:
        if not dog:
            return None
        dog_class, _ = self._class(dog)
        return RelatedDogRead(
            id=dog.public_id,
            name=dog.name,
            birth_date=dog.birth_date,
            lifecycle=self._lifecycle(dog),
            dog_class=dog_class,
        )

    def _grandparents(
        self, parent: Dog | None, dogs_by_id: dict[int, Dog]
    ) -> GrandparentPairRead:
        if not parent or not parent.litter:
            return GrandparentPairRead(mother=None, father=None)
        return GrandparentPairRead(
            mother=self._related(dogs_by_id.get(parent.litter.mother_id or -1)),
            father=self._related(dogs_by_id.get(parent.litter.father_id or -1)),
        )

    def pedigree(self, public_id: UUID) -> DogPedigreeRead | None:
        dogs = self._all_pedigree_dogs()
        dog = next((item for item in dogs if item.public_id == public_id), None)
        if not dog:
            return None
        dogs_by_id = {item.id: item for item in dogs}
        mother = (
            dogs_by_id.get(dog.litter.mother_id)
            if dog.litter and dog.litter.mother_id
            else None
        )
        father = (
            dogs_by_id.get(dog.litter.father_id)
            if dog.litter and dog.litter.father_id
            else None
        )
        siblings = (
            sorted(
                (
                    self._related(item)
                    for item in dogs
                    if item.litter_id == dog.litter_id and item.id != dog.id
                ),
                key=lambda item: item.name if item else "",
            )
            if dog.litter
            else []
        )
        offspring: list[OffspringLitterRead] = []
        for litter in sorted(self._all_litters(), key=lambda row: row.birth_date):
            if litter.mother_id != dog.id and litter.father_id != dog.id:
                continue
            children = sorted(
                (self._related(item) for item in dogs if item.litter_id == litter.id),
                key=lambda item: item.name if item else "",
            )
            offspring.append(
                OffspringLitterRead(
                    code=litter.code,
                    birth_date=litter.birth_date,
                    children=[item for item in children if item is not None],
                )
            )
        return DogPedigreeRead(
            dog_id=dog.public_id,
            mother=self._related(mother),
            father=self._related(father),
            maternal_grandparents=self._grandparents(mother, dogs_by_id),
            paternal_grandparents=self._grandparents(father, dogs_by_id),
            litter=(
                LitterPedigreeRead(
                    code=dog.litter.code,
                    birth_date=dog.litter.birth_date,
                    siblings=[item for item in siblings if item is not None],
                )
                if dog.litter
                else None
            ),
            offspring=offspring,
        )

    def work(self, public_id: UUID) -> DogWorkRead | None:
        dog_id = self.session.scalar(select(Dog.id).where(Dog.public_id == public_id))
        if dog_id is None:
            return None
        rows = self.session.execute(
            select(WorkSession, WorkParticipation)
            .join(WorkParticipation, WorkParticipation.session_id == WorkSession.id)
            .where(
                WorkParticipation.dog_id == dog_id,
                WorkSession.work_date >= self.clock.season_start,
                WorkSession.work_date <= self.clock.season_end,
                scoped_date_filter(
                    WorkSession, self.workspace_id, WorkSession.work_date
                ),
            )
            .order_by(WorkSession.work_date.desc(), WorkSession.distance_km.desc())
        ).all()
        entries = [
            DogWorkEntryRead(
                date=work_session.work_date,
                distance_km=work_session.distance_km,
                activity_type=work_session.activity_type,
                label=work_session.label,
                role=participation.assigned_role,
            )
            for work_session, participation in rows
        ]
        weekly: dict[date, list[int]] = defaultdict(lambda: [0, 0])
        for entry in entries:
            week_start = entry.date - timedelta(days=entry.date.weekday())
            weekly[week_start][0] += 1
            weekly[week_start][1] += entry.distance_km
        totals = summarize_work_distances(entry.distance_km for entry in entries)
        return DogWorkRead(
            dog_id=public_id,
            season_start=self.clock.season_start,
            season_end=self.clock.season_end,
            summary=DogWorkSummaryRead(
                total_km=totals.dog_km,
                starts=totals.dog_starts,
                starts_5km=totals.starts_5km,
                starts_10km=totals.starts_10km,
                last_work_date=max((entry.date for entry in entries), default=None),
                average_km_per_start=(
                    totals.average_km_per_start if totals.dog_starts else None
                ),
            ),
            weekly=[
                DogWeeklyWorkRead(
                    week_start=week_start,
                    starts=values[0],
                    total_km=values[1],
                )
                for week_start, values in sorted(weekly.items(), reverse=True)
            ],
            entries=entries,
        )

    def history(self, public_id: UUID) -> DogHistoryRead | None:
        dog = self._dog(public_id)
        if not dog:
            return None
        reference = self.clock.reference_date
        return DogHistoryRead(
            dog_id=dog.public_id,
            reference_date=reference,
            availability=[
                PeriodHistoryRead(
                    value=period.availability_state,
                    valid_from=period.valid_from,
                    valid_to=period.valid_to,
                    is_current=effective_period([period], reference) is not None,
                    note=period.note,
                )
                for period in sorted(
                    dog.availability_periods, key=lambda row: row.valid_from
                )
            ],
            classes=[
                PeriodHistoryRead(
                    value=period.dog_class,
                    valid_from=period.valid_from,
                    valid_to=period.valid_to,
                    is_current=effective_period([period], reference) is not None,
                )
                for period in sorted(dog.class_periods, key=lambda row: row.valid_from)
            ],
            lifecycle=[
                PeriodHistoryRead(
                    value=period.lifecycle_state,
                    valid_from=period.valid_from,
                    valid_to=period.valid_to,
                    is_current=effective_period([period], reference) is not None,
                )
                for period in sorted(
                    dog.lifecycle_periods, key=lambda row: row.valid_from
                )
            ],
            housing=[
                HousingHistoryRead(
                    location=location_read(assignment.location),
                    valid_from=assignment.valid_from,
                    valid_to=assignment.valid_to,
                    is_current=effective_period([assignment], reference) is not None,
                    note=assignment.note,
                )
                for assignment in sorted(
                    dog.housing_assignments, key=lambda row: row.valid_from
                )
            ],
            archive=self._archive(dog),
        )
