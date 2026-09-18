from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, timedelta
from typing import Final

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.demo_clock import DemoClock
from app.demo.catalog import (
    ARCHIVE_SPECS,
    DEMO_DATASET_VERSION,
    DEMO_RANDOM_SEED,
    DOG_BY_NAME,
    DOG_SPECS,
    HARD_CONFLICT_SPECS,
    HIGH_WORKLOAD_DOGS,
    LITTER_SPECS,
    PREFERRED_PAIR_SPECS,
    RELATIONSHIP_SPECS,
    UNDERUSED_DOGS,
    availability_period_specs,
    class_period_specs,
)
from app.demo.semantic import semantic_checksum
from app.domain.workload import WorkloadRuleViolation, add_daily_dog_distance
from app.models import (
    DemoDataset,
    Dog,
    DogArchive,
    DogAvailabilityPeriod,
    DogClassPeriod,
    DogLifecyclePeriod,
    DogRelationshipConstraint,
    DogRoleCapability,
    HousingAssignment,
    KennelLocation,
    Litter,
    WorkParticipation,
    WorkSession,
)
from app.models.enums import (
    ActivityType,
    AvailabilityState,
    DogClass,
    LifecycleState,
    LocationType,
    WorkingRole,
)

DOMAIN_TABLES: Final[tuple[str, ...]] = (
    "planned_team_slots",
    "planned_teams",
    "planned_activity_participants",
    "planned_activities",
    "daily_plans",
    "work_participations",
    "work_sessions",
    "dog_relationship_constraints",
    "housing_assignments",
    "kennel_locations",
    "dog_role_capabilities",
    "dog_archives",
    "dog_availability_periods",
    "dog_lifecycle_periods",
    "dog_class_periods",
    "litters",
    "dogs",
    "demo_datasets",
)


class DemoResetNotAllowedError(RuntimeError):
    pass


class DemoAlreadySeededError(RuntimeError):
    pass


def assert_reset_is_safe(settings: Settings) -> None:
    database_name = make_url(settings.database_url).database
    if settings.app_env.lower() == "production":
        raise DemoResetNotAllowedError("demo reset is disabled in production")
    if not settings.demo_reset_enabled:
        raise DemoResetNotAllowedError(
            "set DEMO_RESET_ENABLED=true for the app-owned demo database"
        )
    if database_name != "husky_tracking":
        raise DemoResetNotAllowedError(
            f"refusing to reset database {database_name!r}; expected the app-owned "
            "'husky_tracking' database"
        )


def _truncate_domain(session: Session) -> None:
    tables = ", ".join(DOMAIN_TABLES)
    session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def seed_demo_world(
    session: Session, clock: DemoClock, *, require_empty: bool = True
) -> str:
    if require_empty and session.scalar(select(func.count()).select_from(Dog)):
        raise DemoAlreadySeededError(
            "domain data already exists; use python -m app.demo.reset"
        )

    dataset = DemoDataset(version=DEMO_DATASET_VERSION, random_seed=DEMO_RANDOM_SEED)
    session.add(dataset)

    dogs_by_name: dict[str, Dog] = {}
    for spec in DOG_SPECS:
        dog = Dog(
            public_id=spec.public_id,
            name=spec.name,
            birth_date=spec.birth_date,
            sex=spec.sex.value,
            is_neutered=spec.neutered_on is not None,
            neutered_on=spec.neutered_on,
            photo_key=spec.photo_key,
            notes="Fictional canonical demo dog.",
        )
        session.add(dog)
        dogs_by_name[spec.name] = dog
    session.flush()

    litters_by_code: dict[str, Litter] = {}
    for litter_spec in LITTER_SPECS:
        litter = Litter(
            code=litter_spec.code,
            birth_date=litter_spec.birth_date,
            mother_id=(
                dogs_by_name[litter_spec.mother].id if litter_spec.mother else None
            ),
            father_id=(
                dogs_by_name[litter_spec.father].id if litter_spec.father else None
            ),
            notes=litter_spec.notes,
        )
        session.add(litter)
        litters_by_code[litter_spec.code] = litter
    session.flush()
    for spec in DOG_SPECS:
        if spec.litter_code:
            dogs_by_name[spec.name].litter_id = litters_by_code[spec.litter_code].id

    for spec in DOG_SPECS:
        dog = dogs_by_name[spec.name]
        archive = ARCHIVE_SPECS.get(spec.name)
        for dog_class, valid_from, valid_to in class_period_specs(spec):
            session.add(
                DogClassPeriod(
                    dog_id=dog.id,
                    dog_class=dog_class.value,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
            )
        if archive:
            session.add_all(
                [
                    DogLifecyclePeriod(
                        dog_id=dog.id,
                        lifecycle_state=LifecycleState.ACTIVE.value,
                        valid_from=spec.birth_date,
                        valid_to=archive.archive_date,
                    ),
                    DogLifecyclePeriod(
                        dog_id=dog.id,
                        lifecycle_state=LifecycleState.ARCHIVED.value,
                        valid_from=archive.archive_date,
                        valid_to=None,
                    ),
                    DogArchive(
                        dog_id=dog.id,
                        archive_date=archive.archive_date,
                        reason=archive.reason.value,
                        note=archive.note,
                    ),
                ]
            )
        else:
            session.add(
                DogLifecyclePeriod(
                    dog_id=dog.id,
                    lifecycle_state=LifecycleState.ACTIVE.value,
                    valid_from=spec.birth_date,
                    valid_to=None,
                )
            )

        for state, valid_from, valid_to, note in availability_period_specs(
            spec, clock.season_start
        ):
            session.add(
                DogAvailabilityPeriod(
                    dog_id=dog.id,
                    availability_state=state.value,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    note=note,
                )
            )

    locations_by_code = _seed_locations(session)
    _seed_housing(session, clock, dogs_by_name, locations_by_code)
    role_capabilities = _seed_roles(session, dogs_by_name)
    _seed_relationships(session, dogs_by_name)
    _seed_workload(session, clock, dogs_by_name, role_capabilities)
    session.flush()

    from app.demo.validation import validate_demo_world

    validate_demo_world(session, clock)

    checksum = semantic_checksum(session)
    dataset.semantic_checksum = checksum
    session.flush()
    return checksum


def reset_demo_world(
    session: Session,
    clock: DemoClock,
    *,
    settings: Settings | None = None,
    require_enabled: bool = True,
) -> str:
    active_settings = settings or get_settings()
    if require_enabled:
        assert_reset_is_safe(active_settings)
    _truncate_domain(session)
    return seed_demo_world(session, clock, require_empty=False)


def _seed_locations(session: Session) -> dict[str, KennelLocation]:
    locations: dict[str, KennelLocation] = {}
    for zone in ("A", "B"):
        for row in ("1", "2"):
            for position in range(1, 6):
                code = f"{zone}{row}-{position:02d}"
                location = KennelLocation(
                    code=code,
                    display_name=f"{zone}{row} enclosure {position}",
                    location_type=LocationType.ADULT_ENCLOSURE.value,
                    zone=zone,
                    row_label=row,
                    position=position,
                    capacity=2,
                    is_active=True,
                )
                session.add(location)
                locations[code] = location
    for index, code in enumerate(("PUPPY-A", "PUPPY-B"), start=1):
        location = KennelLocation(
            code=code,
            display_name=f"Puppy building {code[-1]}",
            location_type=LocationType.PUPPY_AREA.value,
            zone="PUPPY",
            row_label=code[-1],
            position=index,
            capacity=5,
            is_active=True,
        )
        session.add(location)
        locations[code] = location
    session.flush()
    return locations


def _seed_housing(
    session: Session,
    clock: DemoClock,
    dogs: dict[str, Dog],
    locations: dict[str, KennelLocation],
) -> None:
    adult_codes = [
        f"{zone}{row}-{position:02d}"
        for zone in "AB"
        for row in "12"
        for position in range(1, 6)
    ]
    active_adults = sorted(
        (
            spec
            for spec in DOG_SPECS
            if spec.name not in ARCHIVE_SPECS and spec.birth_date.year <= 2025
        ),
        key=lambda spec: (spec.birth_date, spec.name),
    )
    current_code: dict[str, str] = {
        spec.name: adult_codes[index // 2] for index, spec in enumerate(active_adults)
    }
    moves = (
        (active_adults[0:4], date(2026, 1, 15)),
        (active_adults[4:8], date(2026, 2, 10)),
    )
    moved_names: set[str] = set()
    for group, move_date in moves:
        first_code = current_code[group[0].name]
        second_code = current_code[group[2].name]
        historical = {
            group[0].name: first_code,
            group[2].name: first_code,
            group[1].name: second_code,
            group[3].name: second_code,
        }
        for spec in group:
            moved_names.add(spec.name)
            session.add_all(
                [
                    HousingAssignment(
                        dog_id=dogs[spec.name].id,
                        location_id=locations[historical[spec.name]].id,
                        valid_from=clock.season_start,
                        valid_to=move_date,
                        note="Pre-move demo assignment.",
                    ),
                    HousingAssignment(
                        dog_id=dogs[spec.name].id,
                        location_id=locations[current_code[spec.name]].id,
                        valid_from=move_date,
                        valid_to=None,
                        note="Planned paired housing move.",
                    ),
                ]
            )
    for spec in active_adults:
        if spec.name not in moved_names:
            session.add(
                HousingAssignment(
                    dog_id=dogs[spec.name].id,
                    location_id=locations[current_code[spec.name]].id,
                    valid_from=clock.season_start,
                    valid_to=None,
                    note=None,
                )
            )

    for spec in DOG_SPECS:
        if spec.birth_date.year == 2026:
            code = "PUPPY-A" if spec.litter_code == "T" else "PUPPY-B"
            session.add(
                HousingAssignment(
                    dog_id=dogs[spec.name].id,
                    location_id=locations[code].id,
                    valid_from=spec.birth_date,
                    valid_to=None,
                    note=f"Resident with complete {spec.litter_code}-litter.",
                )
            )

    for index, name in enumerate(sorted(ARCHIVE_SPECS)):
        archive = ARCHIVE_SPECS[name]
        end = min(archive.archive_date, clock.season_start)
        start = max(DOG_BY_NAME[name].birth_date, end - timedelta(days=180))
        session.add(
            HousingAssignment(
                dog_id=dogs[name].id,
                location_id=locations[adult_codes[index // 2]].id,
                valid_from=start,
                valid_to=end,
                note="Retained historical housing before archive.",
            )
        )


def _seed_roles(session: Session, dogs: dict[str, Dog]) -> dict[str, tuple[str, ...]]:
    eligible = sorted(
        spec.name
        for spec in DOG_SPECS
        if spec.birth_date.year <= 2024
        and spec.name not in {"Cinder", "Hilda", "Kismet", "Mabel", "Oona"}
    )
    roles_by_name: dict[str, tuple[str, ...]] = {}
    for index, name in enumerate(eligible):
        roles = [WorkingRole.TEAM.value]
        if index % 3 == 0:
            roles.append(WorkingRole.LEAD.value)
        if index % 2 == 0:
            roles.append(WorkingRole.WHEEL.value)
        roles_by_name[name] = tuple(roles)
        for role in roles:
            session.add(DogRoleCapability(dog_id=dogs[name].id, role=role))
    return roles_by_name


def _seed_relationships(session: Session, dogs: dict[str, Dog]) -> None:
    assert len(PREFERRED_PAIR_SPECS) == 10
    assert len(HARD_CONFLICT_SPECS) == 6
    for first_name, second_name, kind in RELATIONSHIP_SPECS:
        first = dogs[first_name]
        second = dogs[second_name]
        dog_a, dog_b = sorted((first, second), key=lambda dog: dog.id)
        session.add(
            DogRelationshipConstraint(
                dog_a_id=dog_a.id,
                dog_b_id=dog_b.id,
                relationship_kind=kind.value,
                note="Fictional symmetric demo relationship.",
            )
        )


def _class_at(name: str, on_date: date) -> DogClass | None:
    for dog_class, valid_from, valid_to in class_period_specs(DOG_BY_NAME[name]):
        if valid_from <= on_date and (valid_to is None or on_date < valid_to):
            return dog_class
    return None


def _status_at(
    name: str, on_date: date, season_start: date
) -> AvailabilityState | None:
    for state, valid_from, valid_to, _ in availability_period_specs(
        DOG_BY_NAME[name], season_start
    ):
        if valid_from <= on_date and (valid_to is None or on_date < valid_to):
            return state
    return None


def _stable_tie(name: str, work_date: date, distance: int) -> str:
    raw = f"{DEMO_RANDOM_SEED}:{work_date.isoformat()}:{distance}:{name}".encode()
    return hashlib.sha256(raw).hexdigest()


def _seed_workload(
    session: Session,
    clock: DemoClock,
    dogs: dict[str, Dog],
    roles_by_name: dict[str, tuple[str, ...]],
) -> None:
    total_km: dict[str, int] = defaultdict(int)
    starts: dict[str, int] = defaultdict(int)
    last_worked: dict[str, date] = {}

    def eligible(
        name: str,
        work_date: date,
        distance: int,
        worked_today: set[str],
        daily_workload_km: dict[str, int],
    ) -> bool:
        if name in worked_today or name not in roles_by_name:
            return False
        try:
            add_daily_dog_distance(daily_workload_km[name], distance)
        except WorkloadRuleViolation:
            return False
        archive = ARCHIVE_SPECS.get(name)
        if archive and work_date >= archive.archive_date:
            return False
        dog_class = _class_at(name, work_date)
        if dog_class not in {DogClass.TRAINING, DogClass.STANDARD}:
            return False
        if distance == 10 and dog_class != DogClass.STANDARD:
            return False
        return (
            _status_at(name, work_date, clock.season_start)
            == AvailabilityState.AVAILABLE
        )

    def score(name: str, work_date: date, distance: int) -> tuple[float, int, str]:
        weight = (
            1.15
            if name in HIGH_WORKLOAD_DOGS
            else 0.85
            if name in UNDERUSED_DOGS
            else 1.0
        )
        return (
            total_km[name] / weight,
            starts[name],
            _stable_tie(name, work_date, distance),
        )

    current = clock.season_start
    while current <= clock.season_end:
        if current.weekday() in {0, 1, 3, 5}:
            worked_today: set[str] = set()
            daily_workload_km: dict[str, int] = defaultdict(int)
            for distance in (10, 5):
                candidates = [
                    name
                    for name in roles_by_name
                    if eligible(
                        name,
                        current,
                        distance,
                        worked_today,
                        daily_workload_km,
                    )
                ]
                if distance == 5:
                    training = [
                        name
                        for name in candidates
                        if _class_at(name, current) == DogClass.TRAINING
                    ]
                    standard = [
                        name
                        for name in candidates
                        if _class_at(name, current) == DogClass.STANDARD
                    ]
                    training.sort(key=lambda name: score(name, current, distance))
                    training_slots = min(2, len(training))
                    chosen = training[:training_slots]
                    standard_slots = 8 - len(chosen)
                    rested = [
                        name
                        for name in standard
                        if last_worked.get(name) != current - timedelta(days=1)
                    ]
                    pool = rested if len(rested) >= standard_slots else standard
                    pool.sort(key=lambda name: score(name, current, distance))
                    chosen.extend(pool[:standard_slots])
                else:
                    rested = [
                        name
                        for name in candidates
                        if last_worked.get(name) != current - timedelta(days=1)
                    ]
                    pool = rested if len(rested) >= 8 else candidates
                    pool.sort(key=lambda name: score(name, current, distance))
                    chosen = pool[:8]

                if len(chosen) != 8:
                    raise RuntimeError(
                        f"insufficient eligible dogs for {current} {distance} km"
                    )
                work_session = WorkSession(
                    source_reference=f"demo:{current.isoformat()}:{distance}km",
                    work_date=current,
                    distance_km=distance,
                    activity_type=ActivityType.SLED_TRAINING.value,
                    label=f"{distance} km sled training",
                    note="Deterministically generated canonical demo session.",
                )
                session.add(work_session)
                session.flush()
                for name in chosen:
                    roles = roles_by_name[name]
                    role = WorkingRole.TEAM.value
                    if WorkingRole.LEAD.value in roles and starts[name] % 4 == 0:
                        role = WorkingRole.LEAD.value
                    elif WorkingRole.WHEEL.value in roles and starts[name] % 3 == 0:
                        role = WorkingRole.WHEEL.value
                    session.add(
                        WorkParticipation(
                            session_id=work_session.id,
                            dog_id=dogs[name].id,
                            assigned_role=role,
                        )
                    )
                    worked_today.add(name)
                    daily_workload_km[name] = add_daily_dog_distance(
                        daily_workload_km[name], distance
                    )
                    total_km[name] += distance
                    starts[name] += 1
                    last_worked[name] = current
        current += timedelta(days=1)
