from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.demo_clock import DemoClock
from app.demo.catalog import (
    DEMO_DATASET_VERSION,
    FORBIDDEN_STREAMLIT_NAMES,
    HIGH_WORKLOAD_DOGS,
    MINIMUM_BREEDING_AGE_DAYS,
    UNDERUSED_DOGS,
)
from app.demo.semantic import semantic_checksum
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
    AvailabilityState,
    DogClass,
    LifecycleState,
    LocationType,
    RelationshipKind,
)

EXPECTED_COHORTS: dict[int, tuple[int, int]] = {
    2016: (4, 0),
    2017: (0, 0),
    2018: (3, 2),
    2019: (4, 1),
    2020: (4, 1),
    2021: (5, 1),
    2022: (4, 1),
    2023: (5, 1),
    2024: (5, 1),
    2025: (6, 2),
    2026: (10, 0),
}

T = TypeVar("T")


class DemoValidationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("canonical demo validation failed:\n- " + "\n- ".join(errors))
        self.errors = errors


@dataclass(frozen=True, slots=True)
class DemoValidationReport:
    dataset_version: str
    checksum: str
    dog_count: int
    active_count: int
    archived_count: int
    cohort_counts: dict[int, dict[str, int]]
    class_counts: dict[str, int]
    archive_reason_counts: dict[str, int]
    current_status_counts: dict[str, int]
    adult_enclosure_count: int
    puppy_area_count: int
    historical_move_count: int
    session_count: int
    participation_count: int
    distance_session_counts: dict[int, int]
    working_dog_workload_km: dict[str, int]
    workload_min_km: int
    workload_median_km: float
    workload_max_km: int
    litter_rows: tuple[dict[str, Any], ...]


def _effective(period: Any, on_date: date) -> bool:
    return period.valid_from <= on_date and (
        period.valid_to is None or on_date < period.valid_to
    )


def _current(periods: list[T], on_date: date) -> T | None:
    matches = [period for period in periods if _effective(period, on_date)]
    return matches[0] if len(matches) == 1 else None


def _has_overlap(periods: list[Any]) -> bool:
    ordered = sorted(periods, key=lambda period: period.valid_from)
    return any(
        previous.valid_to is None or current.valid_from < previous.valid_to
        for previous, current in zip(ordered, ordered[1:], strict=False)
    )


def validate_demo_world(session: Session, clock: DemoClock) -> DemoValidationReport:
    errors: list[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    dogs = list(session.scalars(select(Dog)))
    dog_by_id = {dog.id: dog for dog in dogs}
    dog_by_name = {dog.name: dog for dog in dogs}
    litters = list(session.scalars(select(Litter)))
    litter_by_id = {litter.id: litter for litter in litters}
    archives = list(session.scalars(select(DogArchive)))
    archive_by_dog = {archive.dog_id: archive for archive in archives}
    class_periods = list(session.scalars(select(DogClassPeriod)))
    lifecycle_periods = list(session.scalars(select(DogLifecyclePeriod)))
    status_periods = list(session.scalars(select(DogAvailabilityPeriod)))
    locations = list(session.scalars(select(KennelLocation)))
    housing = list(session.scalars(select(HousingAssignment)))
    roles = list(session.scalars(select(DogRoleCapability)))
    relations = list(session.scalars(select(DogRelationshipConstraint)))
    work_sessions = list(session.scalars(select(WorkSession)))
    participations = list(session.scalars(select(WorkParticipation)))
    datasets = list(session.scalars(select(DemoDataset)))

    class_by_dog: dict[int, list[DogClassPeriod]] = defaultdict(list)
    lifecycle_by_dog: dict[int, list[DogLifecyclePeriod]] = defaultdict(list)
    status_by_dog: dict[int, list[DogAvailabilityPeriod]] = defaultdict(list)
    housing_by_dog: dict[int, list[HousingAssignment]] = defaultdict(list)
    roles_by_dog: dict[int, set[str]] = defaultdict(set)
    for class_period in class_periods:
        class_by_dog[class_period.dog_id].append(class_period)
    for lifecycle_period in lifecycle_periods:
        lifecycle_by_dog[lifecycle_period.dog_id].append(lifecycle_period)
    for status_period in status_periods:
        status_by_dog[status_period.dog_id].append(status_period)
    for assignment in housing:
        housing_by_dog[assignment.dog_id].append(assignment)
    for role in roles:
        roles_by_dog[role.dog_id].add(role.role)

    expect(len(datasets) == 1, "exactly one demo dataset marker is required")
    if datasets:
        expect(
            datasets[0].version == DEMO_DATASET_VERSION,
            "dataset version is not canonical",
        )
    expect(len(dogs) == 60, f"expected 60 dogs, found {len(dogs)}")
    expect(len({dog.name for dog in dogs}) == len(dogs), "dog names must be unique")
    forbidden = sorted({dog.name for dog in dogs} & FORBIDDEN_STREAMLIT_NAMES)
    expect(not forbidden, f"forbidden Streamlit dog names seeded: {forbidden}")

    active_ids: set[int] = set()
    archived_ids: set[int] = set()
    for dog in dogs:
        expect(
            not _has_overlap(class_by_dog[dog.id]),
            f"overlapping class periods for {dog.name}",
        )
        expect(
            not _has_overlap(lifecycle_by_dog[dog.id]),
            f"overlapping lifecycle periods for {dog.name}",
        )
        expect(
            not _has_overlap(status_by_dog[dog.id]),
            f"overlapping availability periods for {dog.name}",
        )
        expect(
            not _has_overlap(housing_by_dog[dog.id]),
            f"overlapping housing assignments for {dog.name}",
        )
        lifecycle = _current(lifecycle_by_dog[dog.id], clock.reference_date)
        expect(lifecycle is not None, f"no single current lifecycle for {dog.name}")
        if lifecycle and lifecycle.lifecycle_state == LifecycleState.ACTIVE.value:
            active_ids.add(dog.id)
        elif lifecycle and lifecycle.lifecycle_state == LifecycleState.ARCHIVED.value:
            archived_ids.add(dog.id)

    expect(len(active_ids) == 50, f"expected 50 active dogs, found {len(active_ids)}")
    expect(
        len(archived_ids) == 10, f"expected 10 archived dogs, found {len(archived_ids)}"
    )
    expect(
        set(archive_by_dog) == archived_ids,
        "archive metadata must match archived lifecycle",
    )

    cohort_counts: dict[int, dict[str, int]] = {}
    for year, (expected_active, expected_archived) in EXPECTED_COHORTS.items():
        active = sum(
            dog.birth_date.year == year and dog.id in active_ids for dog in dogs
        )
        archived = sum(
            dog.birth_date.year == year and dog.id in archived_ids for dog in dogs
        )
        cohort_counts[year] = {"active": active, "archived": archived}
        expect(
            (active, archived) == (expected_active, expected_archived),
            f"cohort {year} expected {expected_active}/{expected_archived}, "
            f"found {active}/{archived}",
        )

    class_counts: Counter[str] = Counter()
    for dog_id in active_ids:
        current_class = _current(class_by_dog[dog_id], clock.reference_date)
        expect(
            current_class is not None,
            f"active dog {dog_by_id[dog_id].name} has no current class",
        )
        if current_class:
            class_counts[current_class.dog_class] += 1
    expect(
        class_counts
        == Counter(
            {
                DogClass.PUPPY.value: 10,
                DogClass.JUNIOR.value: 6,
                DogClass.TRAINING.value: 8,
                DogClass.STANDARD.value: 26,
            }
        ),
        f"invalid active class distribution: {dict(class_counts)}",
    )

    reason_counts = Counter(archive.reason for archive in archives)
    expect(
        reason_counts
        == Counter({"euthanized": 3, "deceased": 3, "rehomed_to_guide": 4}),
        f"invalid archive reason distribution: {dict(reason_counts)}",
    )

    children_by_litter: dict[int, list[Dog]] = defaultdict(list)
    for dog in dogs:
        if dog.litter_id:
            children_by_litter[dog.litter_id].append(dog)
            litter = litter_by_id[dog.litter_id]
            expect(
                dog.birth_date == litter.birth_date,
                f"{dog.name} birth date differs from litter {litter.code}",
            )
            expect(
                dog.name.upper().startswith(litter.code.upper()),
                f"{dog.name} does not begin with litter code {litter.code}",
            )
    expect(len(litters) == 10, f"expected 10 litters, found {len(litters)}")
    expect(
        len({litter.code for litter in litters}) == len(litters),
        "litter codes must be unique",
    )

    parent_graph: dict[int, tuple[int, ...]] = {}
    for litter in litters:
        parents = tuple(
            parent_id for parent_id in (litter.mother_id, litter.father_id) if parent_id
        )
        expect(
            litter.mother_id != litter.father_id,
            f"litter {litter.code} has identical parents",
        )
        if litter.mother_id:
            mother = dog_by_id[litter.mother_id]
            expect(mother.sex == "female", f"litter {litter.code} mother is not female")
            expect(
                (litter.birth_date - mother.birth_date).days
                >= MINIMUM_BREEDING_AGE_DAYS,
                f"litter {litter.code} mother is too young",
            )
            archive = archive_by_dog.get(mother.id)
            expect(
                archive is None or archive.archive_date > litter.birth_date,
                f"litter {litter.code} was born after its mother's archive date",
            )
        if litter.father_id:
            father = dog_by_id[litter.father_id]
            expect(father.sex == "male", f"litter {litter.code} father is not male")
            expect(
                (litter.birth_date - father.birth_date).days
                >= MINIMUM_BREEDING_AGE_DAYS,
                f"litter {litter.code} father is too young",
            )
            archive = archive_by_dog.get(father.id)
            expect(
                archive is None or archive.archive_date > litter.birth_date,
                f"litter {litter.code} was born after its father's archive date",
            )
        for child in children_by_litter[litter.id]:
            expect(child.id not in parents, f"{child.name} is its own parent")
            parent_graph[child.id] = parents

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(dog_id: int) -> None:
        if dog_id in visiting:
            errors.append(f"pedigree cycle detected at {dog_by_id[dog_id].name}")
            return
        if dog_id in visited:
            return
        visiting.add(dog_id)
        for parent_id in parent_graph.get(dog_id, ()):
            visit(parent_id)
        visiting.remove(dog_id)
        visited.add(dog_id)

    for dog in dogs:
        visit(dog.id)

    def depth(dog_id: int, path: frozenset[int] = frozenset()) -> int:
        if dog_id in path:
            return 0
        parents = parent_graph.get(dog_id, ())
        return (
            0
            if not parents
            else 1 + max(depth(parent_id, path | {dog_id}) for parent_id in parents)
        )

    expect(
        max((depth(dog.id) for dog in dogs), default=0) >= 2,
        "three pedigree generations missing",
    )
    archived_parent_ids = {
        parent_id
        for child_id, parents in parent_graph.items()
        if child_id in active_ids
        for parent_id in parents
        if parent_id in archived_ids
    }
    expect(bool(archived_parent_ids), "no archived parent of an active dog")
    active_with_grandparent = any(
        child_id in active_ids
        and any(parent_graph.get(parent_id) for parent_id in parents)
        for child_id, parents in parent_graph.items()
    )
    expect(active_with_grandparent, "no active dog has a represented grandparent")
    archived_grandparent_ids = {
        grandparent_id
        for child_id, parent_ids in parent_graph.items()
        if child_id in active_ids
        for parent_id in parent_ids
        for grandparent_id in parent_graph.get(parent_id, ())
        if grandparent_id in archived_ids
    }
    expect(
        bool(archived_grandparent_ids),
        "no archived dog has an active represented grandchild",
    )

    status_counts: Counter[str] = Counter()
    for dog_id in active_ids:
        status = _current(status_by_dog[dog_id], clock.reference_date)
        expect(
            status is not None,
            f"active dog {dog_by_id[dog_id].name} has no current status",
        )
        if status:
            status_counts[status.availability_state] += 1
    for state in AvailabilityState:
        expect(
            status_counts[state.value] >= 1, f"no current {state.value} status example"
        )

    adult_locations = [
        location
        for location in locations
        if location.location_type == LocationType.ADULT_ENCLOSURE.value
    ]
    puppy_locations = [
        location
        for location in locations
        if location.location_type == LocationType.PUPPY_AREA.value
    ]
    expect(
        len(adult_locations) == 20,
        f"expected 20 adult enclosures, found {len(adult_locations)}",
    )
    expect(
        len(puppy_locations) == 2,
        f"expected 2 puppy areas, found {len(puppy_locations)}",
    )
    expect(
        all(location.capacity == 2 for location in adult_locations),
        "adult capacity must be two",
    )
    expect(
        all(location.capacity == 5 for location in puppy_locations),
        "puppy capacity must be five",
    )

    assignments_by_location: dict[int, list[HousingAssignment]] = defaultdict(list)
    for assignment in housing:
        assignments_by_location[assignment.location_id].append(assignment)
    for location in locations:
        events: list[tuple[date, int]] = []
        for assignment in assignments_by_location[location.id]:
            events.append((assignment.valid_from, 1))
            if assignment.valid_to:
                events.append((assignment.valid_to, -1))
        occupancy = 0
        for _, change in sorted(events, key=lambda event: (event[0], event[1])):
            occupancy += change
            expect(
                occupancy <= location.capacity,
                f"historical capacity exceeded at {location.code}",
            )

    current_occupancy: Counter[int] = Counter()
    current_housed_ids: set[int] = set()
    for assignment in housing:
        if _effective(assignment, clock.reference_date):
            current_occupancy[assignment.location_id] += 1
            current_housed_ids.add(assignment.dog_id)
    expect(
        all(current_occupancy[location.id] == 2 for location in adult_locations),
        "every adult enclosure must hold exactly two dogs",
    )
    expect(
        all(current_occupancy[location.id] == 5 for location in puppy_locations),
        "every puppy area must hold exactly five puppies",
    )
    active_non_puppy_ids = {
        dog.id for dog in dogs if dog.id in active_ids and dog.birth_date.year != 2026
    }
    active_puppy_ids = {
        dog.id for dog in dogs if dog.id in active_ids and dog.birth_date.year == 2026
    }
    expect(
        current_housed_ids == active_ids,
        "current housing must contain every active dog and no archived dog",
    )
    adult_location_ids = {location.id for location in adult_locations}
    puppy_location_ids = {location.id for location in puppy_locations}
    expect(
        {
            assignment.dog_id
            for assignment in housing
            if assignment.location_id in adult_location_ids
            and _effective(assignment, clock.reference_date)
        }
        == active_non_puppy_ids,
        "adult enclosures must contain exactly the 40 active non-puppies",
    )
    expect(
        {
            assignment.dog_id
            for assignment in housing
            if assignment.location_id in puppy_location_ids
            and _effective(assignment, clock.reference_date)
        }
        == active_puppy_ids,
        "puppy areas must contain exactly the 10 active 2026 puppies",
    )

    preferred_count = sum(
        relation.relationship_kind == RelationshipKind.PREFERRED_PAIR.value
        for relation in relations
    )
    conflict_count = sum(
        relation.relationship_kind == RelationshipKind.HARD_CONFLICT.value
        for relation in relations
    )
    expect(
        preferred_count == 10, f"expected 10 preferred pairs, found {preferred_count}"
    )
    expect(conflict_count == 6, f"expected 6 conflicts, found {conflict_count}")
    expect(
        all(relation.dog_a_id < relation.dog_b_id for relation in relations),
        "relationship pairs are not canonically ordered",
    )

    work_session_by_id = {
        work_session.id: work_session for work_session in work_sessions
    }
    participation_counts = Counter(
        participation.session_id for participation in participations
    )
    expect(
        all(count == 8 for count in participation_counts.values()),
        "every generated work session must contain eight starts",
    )
    workload_km: Counter[int] = Counter()
    for work_session in work_sessions:
        expect(
            clock.season_start <= work_session.work_date <= clock.season_end,
            f"work session {work_session.source_reference} is outside demo season",
        )
        expect(work_session.distance_km in {5, 10}, "non-canonical work distance found")
    for participation in participations:
        work_session = work_session_by_id[participation.session_id]
        dog = dog_by_id[participation.dog_id]
        lifecycle = _current(lifecycle_by_dog[dog.id], work_session.work_date)
        dog_class = _current(class_by_dog[dog.id], work_session.work_date)
        status = _current(status_by_dog[dog.id], work_session.work_date)
        expect(
            lifecycle is not None
            and lifecycle.lifecycle_state == LifecycleState.ACTIVE.value,
            f"{dog.name} worked outside active lifecycle on {work_session.work_date}",
        )
        expect(
            status is not None
            and status.availability_state == AvailabilityState.AVAILABLE.value,
            f"{dog.name} worked while unavailable on {work_session.work_date}",
        )
        expect(
            dog_class is not None
            and dog_class.dog_class
            in {DogClass.TRAINING.value, DogClass.STANDARD.value},
            f"{dog.name} worked in ineligible class on {work_session.work_date}",
        )
        if dog_class and dog_class.dog_class == DogClass.TRAINING.value:
            expect(
                work_session.distance_km == 5, f"training dog {dog.name} received 10 km"
            )
        expect(
            participation.assigned_role in roles_by_dog[dog.id],
            f"{dog.name} worked an unsupported role",
        )
        workload_km[dog.id] += work_session.distance_km

    for dog in dogs:
        if dog.birth_date.year in {2025, 2026}:
            expect(workload_km[dog.id] == 0, f"puppy/junior {dog.name} has work starts")

    working_ids: set[int] = set()
    standard_ids: set[int] = set()
    for dog_id in active_ids:
        current_class = _current(class_by_dog[dog_id], clock.reference_date)
        if current_class and current_class.dog_class in {
            DogClass.TRAINING.value,
            DogClass.STANDARD.value,
        }:
            working_ids.add(dog_id)
        if current_class and current_class.dog_class == DogClass.STANDARD.value:
            standard_ids.add(dog_id)
    working_values = [workload_km[dog_id] for dog_id in working_ids]
    expect(
        bool(working_values) and min(working_values) > 0,
        "an eligible working dog has no workload",
    )
    if working_values:
        comparable_mean = sum(workload_km[dog_id] for dog_id in standard_ids) / len(
            standard_ids
        )
        persona_names = HIGH_WORKLOAD_DOGS | UNDERUSED_DOGS
        if persona_names <= set(dog_by_name):
            high_values = [
                workload_km[dog_by_name[name].id] for name in HIGH_WORKLOAD_DOGS
            ]
            under_values = [
                workload_km[dog_by_name[name].id] for name in UNDERUSED_DOGS
            ]
            expect(
                sum(high_values) / len(high_values) > comparable_mean,
                "high-workload examples not above the standard-class mean",
            )
            expect(
                sum(under_values) / len(under_values) < comparable_mean,
                "underused examples not below the standard-class mean",
            )
        else:
            expect(False, "canonical workload persona name is missing")

    if errors:
        raise DemoValidationError(errors)

    litter_rows = tuple(
        {
            "code": litter.code,
            "birth_date": litter.birth_date.isoformat(),
            "mother": dog_by_id[litter.mother_id].name if litter.mother_id else None,
            "father": dog_by_id[litter.father_id].name if litter.father_id else None,
            "members": [
                dog.name
                for dog in sorted(
                    children_by_litter[litter.id], key=lambda dog: dog.name
                )
            ],
        }
        for litter in sorted(litters, key=lambda litter: litter.birth_date)
    )
    named_workload = {
        dog_by_id[dog_id].name: workload_km[dog_id]
        for dog_id in sorted(working_ids, key=lambda dog_id: dog_by_id[dog_id].name)
    }
    return DemoValidationReport(
        dataset_version=DEMO_DATASET_VERSION,
        checksum=semantic_checksum(session),
        dog_count=len(dogs),
        active_count=len(active_ids),
        archived_count=len(archived_ids),
        cohort_counts=cohort_counts,
        class_counts=dict(sorted(class_counts.items())),
        archive_reason_counts=dict(sorted(reason_counts.items())),
        current_status_counts=dict(sorted(status_counts.items())),
        adult_enclosure_count=len(adult_locations),
        puppy_area_count=len(puppy_locations),
        historical_move_count=sum(len(rows) > 1 for rows in housing_by_dog.values()),
        session_count=len(work_sessions),
        participation_count=len(participations),
        distance_session_counts=dict(
            sorted(Counter(row.distance_km for row in work_sessions).items())
        ),
        working_dog_workload_km=named_workload,
        workload_min_km=min(working_values),
        workload_median_km=median(working_values),
        workload_max_km=max(working_values),
        litter_rows=litter_rows,
    )
