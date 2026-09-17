from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.demo_clock import DemoClock
from app.domain.workload import (
    MAX_DAILY_DOG_DISTANCE_KM,
    WorkloadRuleViolation,
    add_daily_dog_distance,
)
from app.models import (
    DailyPlan,
    Dog,
    DogRelationshipConstraint,
    HousingAssignment,
    KennelLocation,
    PlannedActivity,
    WorkParticipation,
    WorkSession,
)
from app.models.enums import (
    AvailabilityState,
    DogClass,
    LifecycleState,
    PlannedActivityType,
    RelationshipKind,
)
from app.schemas.daily_entry import (
    ActualEligibilityRead,
    ActualEligibleDogRead,
    ActualParticipantRead,
    ActualParticipantWrite,
    ActualSessionCreate,
    ActualSessionRead,
    ActualSessionUpdate,
    DailyDogRead,
    DailyEntryRead,
    DailyEntrySummaryRead,
    DailyHousingGroupRead,
    PlannedActivityActualRead,
)
from app.services.daily_plan_service import DailyPlanService
from app.services.effective_state import EffectiveDogState


class DailyEntryError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DailyEntryService:
    """Canonical actual-work reads and mutations for one demo-season date."""

    def __init__(self, session: Session, clock: DemoClock) -> None:
        self.session = session
        self.clock = clock
        self.plans = DailyPlanService(session, clock)

    def read(self, work_date: date) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        dogs = self._all_dogs()
        dogs_by_id = {dog.id: dog for dog in dogs}
        sessions = self._sessions(work_date)
        plan = self.plans._plan(work_date)
        sessions_by_plan = {
            item.planned_activity_id: item
            for item in sessions
            if item.planned_activity_id is not None
        }
        session_reads = [self._session_read(item, dogs_by_id) for item in sessions]
        plan_reads = self._plan_reads(plan, sessions_by_plan)
        starts_by_dog: dict[int, int] = defaultdict(int)
        km_by_dog: dict[int, int] = defaultdict(int)
        for work_session in sessions:
            for participation in work_session.participations:
                starts_by_dog[participation.dog_id] += 1
                km_by_dog[participation.dog_id] += work_session.distance_km
        return DailyEntryRead(
            selected_date=work_date,
            season_start=self.clock.season_start,
            season_end=self.clock.season_end,
            reference_date=self.clock.reference_date,
            plan_exists=plan is not None,
            planned_activities=plan_reads,
            sessions=session_reads,
            summary=DailyEntrySummaryRead(
                actual_sessions=len(sessions),
                dogs_worked=len(starts_by_dog),
                dog_starts=sum(starts_by_dog.values()),
                total_dog_km=sum(km_by_dog.values()),
            ),
            housing_groups=self._housing_groups(
                dogs, work_date, starts_by_dog, km_by_dog
            ),
        )

    def eligibility(
        self,
        work_date: date,
        distance_km: int,
        *,
        exclude_session_id: UUID | None = None,
    ) -> ActualEligibilityRead:
        self.plans.validate_date(work_date)
        if distance_km not in {5, 10}:
            raise DailyEntryError(
                "unsupported_distance", "Actual distance must be 5 km or 10 km."
            )
        excluded_internal_id = None
        if exclude_session_id is not None:
            excluded = self._required_session(work_date, exclude_session_id)
            excluded_internal_id = excluded.id
        totals = self._daily_totals(work_date, excluded_internal_id)
        reads = [
            self._eligibility_read(dog, work_date, distance_km, totals.get(dog.id, 0))
            for dog in self._all_dogs()
        ]
        reads.sort(key=lambda item: (not item.eligible, item.name.casefold()))
        return ActualEligibilityRead(
            selected_date=work_date,
            distance_km=distance_km,
            max_daily_km=MAX_DAILY_DOG_DISTANCE_KM,
            dogs=reads,
        )

    def create_manual(
        self, work_date: date, payload: ActualSessionCreate
    ) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        dogs = self._validate_participants(
            work_date, payload.participants, payload.distance_km
        )
        public_id = uuid4()
        work_session = WorkSession(
            public_id=public_id,
            source_reference=f"manual:{public_id.hex}",
            work_date=work_date,
            start_time=payload.start_time,
            distance_km=payload.distance_km,
            activity_type="sled_training",
            label=payload.label,
            note=payload.note,
            revision=1,
        )
        self._replace_participations(work_session, payload.participants, dogs)
        self.session.add(work_session)
        self.session.flush()
        return self.read(work_date)

    def update(
        self,
        work_date: date,
        session_id: UUID,
        payload: ActualSessionUpdate,
    ) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        work_session = self._required_session(work_date, session_id, for_update=True)
        self._check_revision(work_session, payload.expected_revision)
        dogs = self._validate_participants(
            work_date,
            payload.participants,
            payload.distance_km,
            exclude_session_id=work_session.id,
        )
        work_session.start_time = payload.start_time
        work_session.distance_km = payload.distance_km
        work_session.label = payload.label
        work_session.note = payload.note
        self._replace_participations(work_session, payload.participants, dogs)
        self._touch(work_session)
        self.session.flush()
        return self.read(work_date)

    def delete(
        self, work_date: date, session_id: UUID, expected_revision: int
    ) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        work_session = self._required_session(work_date, session_id, for_update=True)
        self._check_revision(work_session, expected_revision)
        self.session.delete(work_session)
        self.session.flush()
        return self.read(work_date)

    def confirm_plan(self, work_date: date, activity_id: UUID) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        plan = self.plans._required_plan(work_date)
        activity = self.plans._required_activity(plan, activity_id)
        if activity.activity_type != PlannedActivityType.TRAINING.value:
            raise DailyEntryError(
                "training_required",
                "Only a planned Training activity can create sled actual work.",
            )
        existing = self.session.scalar(
            select(WorkSession).where(WorkSession.planned_activity_id == activity.id)
        )
        if existing is not None:
            return self.read(work_date)
        assert activity.distance_km is not None
        participant_writes = self._planned_participants(activity)
        dogs = self._validate_participants(
            work_date, participant_writes, activity.distance_km
        )
        public_id = uuid4()
        work_session = WorkSession(
            public_id=public_id,
            source_reference=f"plan:{activity.public_id}",
            planned_activity_id=activity.id,
            work_date=work_date,
            start_time=activity.start_time,
            distance_km=activity.distance_km,
            activity_type="sled_training",
            label=activity.title,
            note=activity.notes[:255] if activity.notes else None,
            revision=1,
        )
        self._replace_participations(work_session, participant_writes, dogs)
        self.session.add(work_session)
        if activity.actual_not_run:
            activity.actual_not_run = False
            self.plans._touch(plan)
        self.session.flush()
        return self.read(work_date)

    def mark_not_run(self, work_date: date, activity_id: UUID) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        plan = self.plans._required_plan(work_date)
        activity = self.plans._required_activity(plan, activity_id)
        if activity.activity_type != PlannedActivityType.TRAINING.value:
            raise DailyEntryError(
                "training_required", "Only Training activities can be marked not run."
            )
        if self.session.scalar(
            select(WorkSession.id).where(WorkSession.planned_activity_id == activity.id)
        ):
            raise DailyEntryError(
                "actual_exists",
                "Delete the linked actual session before marking this plan not run.",
                409,
            )
        if not activity.actual_not_run:
            activity.actual_not_run = True
            self.plans._touch(plan)
        self.session.flush()
        return self.read(work_date)

    def clear_not_run(self, work_date: date, activity_id: UUID) -> DailyEntryRead:
        self.plans.validate_date(work_date)
        plan = self.plans._required_plan(work_date)
        activity = self.plans._required_activity(plan, activity_id)
        if activity.actual_not_run:
            activity.actual_not_run = False
            self.plans._touch(plan)
        self.session.flush()
        return self.read(work_date)

    def _all_dogs(self) -> list[Dog]:
        return list(
            self.session.scalars(
                select(Dog).options(
                    selectinload(Dog.class_periods),
                    selectinload(Dog.lifecycle_periods),
                    selectinload(Dog.availability_periods),
                    selectinload(Dog.role_capabilities),
                    selectinload(Dog.housing_assignments).selectinload(
                        HousingAssignment.location
                    ),
                )
            ).unique()
        )

    def _sessions(self, work_date: date) -> list[WorkSession]:
        return list(
            self.session.scalars(
                select(WorkSession)
                .where(WorkSession.work_date == work_date)
                .options(
                    selectinload(WorkSession.participations).selectinload(
                        WorkParticipation.dog
                    ),
                    selectinload(WorkSession.planned_activity),
                )
                .order_by(
                    WorkSession.start_time.asc().nulls_last(),
                    WorkSession.distance_km.desc(),
                    WorkSession.source_reference,
                )
            ).unique()
        )

    def _required_session(
        self, work_date: date, public_id: UUID, *, for_update: bool = False
    ) -> WorkSession:
        statement = select(WorkSession).where(
            WorkSession.public_id == public_id, WorkSession.work_date == work_date
        )
        if for_update:
            statement = statement.with_for_update()
        work_session = self.session.scalar(statement)
        if work_session is None:
            raise DailyEntryError("session_not_found", "Actual session not found.", 404)
        return work_session

    @staticmethod
    def _check_revision(work_session: WorkSession, expected_revision: int) -> None:
        if work_session.revision != expected_revision:
            raise DailyEntryError(
                "actual_changed",
                "This actual session changed. Reload it before saving.",
                409,
            )

    @staticmethod
    def _touch(work_session: WorkSession) -> None:
        work_session.revision += 1
        work_session.updated_at = datetime.now(UTC)

    def _daily_totals(
        self, work_date: date, exclude_session_id: int | None = None
    ) -> dict[int, int]:
        statement = (
            select(
                WorkParticipation.dog_id,
                func.sum(WorkSession.distance_km),
            )
            .join(WorkSession)
            .where(WorkSession.work_date == work_date)
            .group_by(WorkParticipation.dog_id)
        )
        if exclude_session_id is not None:
            statement = statement.where(WorkSession.id != exclude_session_id)
        return {
            dog_id: int(total or 0) for dog_id, total in self.session.execute(statement)
        }

    def _eligibility_read(
        self, dog: Dog, work_date: date, distance_km: int, current_km: int
    ) -> ActualEligibleDogRead:
        state = EffectiveDogState(work_date)
        dog_class, _ = state.dog_class(dog)
        lifecycle = state.lifecycle(dog)
        availability = state.availability(dog)
        housing = state.housing(dog)
        reasons: list[str] = []
        if dog.birth_date > work_date:
            reasons.append("Not yet born")
        elif lifecycle != LifecycleState.ACTIVE.value:
            reasons.append("Archived" if lifecycle == "archived" else "Not active")
        elif availability != AvailabilityState.AVAILABLE.value:
            reasons.append(self._availability_label(availability))
        elif dog_class == DogClass.PUPPY.value:
            reasons.append("Puppy")
        elif dog_class == DogClass.JUNIOR.value:
            reasons.append("Junior")
        elif dog_class == DogClass.TRAINING.value and distance_km == 10:
            reasons.append("Training class · 5 km only")
        elif dog_class not in {DogClass.TRAINING.value, DogClass.STANDARD.value}:
            reasons.append("Not eligible for regular sled training")
        else:
            try:
                add_daily_dog_distance(current_km, distance_km)
            except WorkloadRuleViolation:
                reasons.append("30 km actual limit reached")
        return ActualEligibleDogRead(
            id=dog.public_id,
            name=dog.name,
            housing_code=housing.location.code if housing else None,
            dog_class=dog_class,
            availability=availability,
            capabilities=sorted(item.role for item in dog.role_capabilities),
            actual_km_today=current_km,
            eligible=not reasons,
            reasons=reasons,
        )

    def _validate_participants(
        self,
        work_date: date,
        writes: list[ActualParticipantWrite],
        distance_km: int,
        *,
        exclude_session_id: int | None = None,
    ) -> dict[UUID, Dog]:
        dogs = self._all_dogs()
        by_public_id = {dog.public_id: dog for dog in dogs}
        totals = self._daily_totals(work_date, exclude_session_id)
        selected: dict[UUID, Dog] = {}
        for item in writes:
            dog = by_public_id.get(item.dog_id)
            if dog is None:
                raise DailyEntryError(
                    "participant_not_found", "One or more selected dogs do not exist."
                )
            eligibility = self._eligibility_read(
                dog, work_date, distance_km, totals.get(dog.id, 0)
            )
            if not eligibility.eligible:
                raise DailyEntryError(
                    "dog_not_eligible",
                    f"{dog.name} cannot be recorded: {eligibility.reasons[0]}.",
                )
            roles = {role.role for role in dog.role_capabilities}
            if item.assigned_role and item.assigned_role not in roles:
                raise DailyEntryError(
                    "role_mismatch",
                    f"{dog.name} is not {item.assigned_role}-capable.",
                )
            selected[item.dog_id] = dog
        self._validate_positioned_pairs(writes, selected)
        return selected

    def _validate_positioned_pairs(
        self, writes: list[ActualParticipantWrite], dogs: dict[UUID, Dog]
    ) -> None:
        positioned = [item for item in writes if item.actual_team_sequence is not None]
        pair_members: dict[tuple[int, int], list[ActualParticipantWrite]] = defaultdict(
            list
        )
        for item in positioned:
            assert item.actual_team_sequence is not None and item.pair_index is not None
            pair_members[(item.actual_team_sequence, item.pair_index)].append(item)
        for members in pair_members.values():
            if len({item.assigned_role for item in members}) > 1:
                raise DailyEntryError(
                    "invalid_geometry", "Dogs in one harness pair must share a role."
                )
        dog_ids = [dogs[item.dog_id].id for item in positioned]
        if len(dog_ids) < 2:
            return
        conflicts = self.session.scalars(
            select(DogRelationshipConstraint).where(
                DogRelationshipConstraint.relationship_kind
                == RelationshipKind.HARD_CONFLICT.value,
                DogRelationshipConstraint.dog_a_id.in_(dog_ids),
                DogRelationshipConstraint.dog_b_id.in_(dog_ids),
            )
        )
        conflicts_by_pair = {
            frozenset((item.dog_a_id, item.dog_b_id)) for item in conflicts
        }
        for members in pair_members.values():
            if len(members) != 2:
                continue
            dog_pair = frozenset(dogs[item.dog_id].id for item in members)
            if dog_pair in conflicts_by_pair:
                first, second = (dogs[item.dog_id].name for item in members)
                raise DailyEntryError(
                    "hard_pair_conflict", f"Cannot pair {first} with {second}."
                )

    def _replace_participations(
        self,
        work_session: WorkSession,
        writes: list[ActualParticipantWrite],
        dogs: dict[UUID, Dog],
    ) -> None:
        if work_session.id is not None and work_session.participations:
            work_session.participations.clear()
            self.session.flush()
        work_session.participations = [
            WorkParticipation(
                dog_id=dogs[item.dog_id].id,
                assigned_role=item.assigned_role,
                actual_team_sequence=item.actual_team_sequence,
                pair_index=item.pair_index,
                side=item.side,
                position_order=item.position_order,
            )
            for item in writes
        ]

    @staticmethod
    def _planned_participants(
        activity: PlannedActivity,
    ) -> list[ActualParticipantWrite]:
        if activity.teams:
            return [
                ActualParticipantWrite(
                    dog_id=slot.dog.public_id,
                    assigned_role=slot.harness_role,
                    actual_team_sequence=team.sequence,
                    pair_index=slot.pair_index,
                    side=slot.side,
                    position_order=slot.position_order,
                )
                for team in sorted(activity.teams, key=lambda item: item.sequence)
                for slot in sorted(team.slots, key=lambda item: item.position_order)
            ]
        return [
            ActualParticipantWrite(dog_id=participant.dog.public_id)
            for participant in activity.participants
        ]

    def _session_read(
        self, work_session: WorkSession, dogs_by_id: dict[int, Dog]
    ) -> ActualSessionRead:
        plan_status = None
        deviations: list[str] = []
        if work_session.planned_activity is not None:
            plan_status, deviations = self._compare_plan_actual(
                work_session.planned_activity, work_session
            )
        source = (
            "planned"
            if work_session.planned_activity_id is not None
            else "seeded"
            if work_session.source_reference.startswith("demo:")
            else "unlinked"
            if work_session.source_reference.startswith("plan:")
            else "manual"
        )
        state = EffectiveDogState(work_session.work_date)
        participants = []
        for item in sorted(
            work_session.participations,
            key=lambda row: (
                row.actual_team_sequence or 999,
                row.position_order or 999,
                row.dog.name.casefold(),
            ),
        ):
            dog = dogs_by_id[item.dog_id]
            housing = state.housing(dog)
            dog_class, _ = state.dog_class(dog)
            participants.append(
                ActualParticipantRead(
                    dog_id=dog.public_id,
                    dog_name=dog.name,
                    housing_code=housing.location.code if housing else None,
                    dog_class=dog_class,
                    availability=state.availability(dog),
                    assigned_role=item.assigned_role,
                    actual_team_sequence=item.actual_team_sequence,
                    pair_index=item.pair_index,
                    pair_label=self._pair_label(item),
                    side=item.side,
                    position_order=item.position_order,
                )
            )
        return ActualSessionRead(
            id=work_session.public_id,
            revision=work_session.revision,
            work_date=work_session.work_date,
            start_time=work_session.start_time,
            distance_km=work_session.distance_km,
            label=work_session.label,
            note=work_session.note,
            source=source,
            planned_activity_id=(
                work_session.planned_activity.public_id
                if work_session.planned_activity
                else None
            ),
            planned_activity_title=(
                work_session.planned_activity.title
                if work_session.planned_activity
                else None
            ),
            plan_status=plan_status,
            deviations=deviations,
            team_count=len(
                {
                    item.actual_team_sequence
                    for item in work_session.participations
                    if item.actual_team_sequence is not None
                }
            ),
            participants=participants,
        )

    def _plan_reads(
        self,
        plan: DailyPlan | None,
        sessions_by_plan: dict[int, WorkSession],
    ) -> list[PlannedActivityActualRead]:
        if plan is None:
            return []
        result: list[PlannedActivityActualRead] = []
        for activity in sorted(plan.activities, key=lambda item: item.sequence):
            actual = sessions_by_plan.get(activity.id)
            deviations: list[str]
            if activity.activity_type != PlannedActivityType.TRAINING.value:
                status, deviations = "context_only", []
            elif actual is not None:
                status, deviations = self._compare_plan_actual(activity, actual)
            elif activity.actual_not_run:
                status, deviations = "not_run", ["Planned training did not run"]
            else:
                status, deviations = "not_recorded", []
            result.append(
                PlannedActivityActualRead(
                    id=activity.public_id,
                    activity_type=activity.activity_type,
                    title=activity.title,
                    start_time=activity.start_time,
                    distance_km=activity.distance_km,
                    participant_count=len(activity.participants),
                    team_count=len(activity.teams),
                    arranged_dog_count=sum(len(team.slots) for team in activity.teams),
                    actual_status=status,
                    actual_session_id=actual.public_id if actual else None,
                    deviations=deviations,
                )
            )
        return result

    @staticmethod
    def _compare_plan_actual(
        activity: PlannedActivity, work_session: WorkSession
    ) -> tuple[str, list[str]]:
        deviations: list[str] = []
        if activity.distance_km != work_session.distance_km:
            deviations.append(f"Distance changed to {work_session.distance_km} km")
        planned: dict[int, tuple[int, int, str, str] | None]
        if activity.teams:
            planned = {
                slot.dog_id: (
                    team.sequence,
                    slot.pair_index,
                    slot.side,
                    slot.harness_role,
                )
                for team in activity.teams
                for slot in team.slots
            }
        else:
            planned = {
                participant.dog_id: None for participant in activity.participants
            }
        actual = {item.dog_id: item for item in work_session.participations}
        missing = set(planned) - set(actual)
        added = set(actual) - set(planned)
        substitutions = min(len(missing), len(added))
        if substitutions:
            deviations.append(
                f"{substitutions} dog{'s' if substitutions != 1 else ''} substituted"
            )
        if len(missing) > substitutions:
            count = len(missing) - substitutions
            deviations.append(
                f"{count} planned dog{'s' if count != 1 else ''} did not run"
            )
        if len(added) > substitutions:
            count = len(added) - substitutions
            deviations.append(f"{count} unplanned dog{'s' if count != 1 else ''} added")
        if activity.teams and not missing and not added:
            actual_geometry = {
                item.dog_id: (
                    item.actual_team_sequence,
                    item.pair_index,
                    item.side,
                    item.assigned_role,
                )
                for item in work_session.participations
            }
            if planned != actual_geometry:
                deviations.append("Harness positions changed")
        if not activity.teams:
            deviations.append("No saved planned lineup")
        substantive = [item for item in deviations if item != "No saved planned lineup"]
        return ("modified" if substantive else "matches_plan"), deviations

    def _housing_groups(
        self,
        dogs: list[Dog],
        work_date: date,
        starts_by_dog: dict[int, int],
        km_by_dog: dict[int, int],
    ) -> list[DailyHousingGroupRead]:
        locations = list(
            self.session.scalars(
                select(KennelLocation).where(KennelLocation.is_active.is_(True))
            )
        )
        locations_by_id = {item.id: item for item in locations}
        state = EffectiveDogState(work_date)
        grouped: dict[int | None, list[DailyDogRead]] = defaultdict(list)
        for dog in dogs:
            if dog.birth_date > work_date or state.lifecycle(dog) != "active":
                continue
            housing = state.housing(dog)
            dog_class, _ = state.dog_class(dog)
            grouped[housing.location_id if housing else None].append(
                DailyDogRead(
                    id=dog.public_id,
                    name=dog.name,
                    housing_code=(housing.location.code if housing else None),
                    dog_class=dog_class,
                    availability=state.availability(dog),
                    starts=starts_by_dog.get(dog.id, 0),
                    actual_km=km_by_dog.get(dog.id, 0),
                )
            )
        result = []
        for location_id, group_dogs in grouped.items():
            location = locations_by_id.get(location_id) if location_id else None
            result.append(
                DailyHousingGroupRead(
                    code=location.code if location else "NO-HOUSING",
                    display_name=location.display_name if location else "No housing",
                    zone=location.zone if location else "UNASSIGNED",
                    row=location.row_label if location else "—",
                    position=location.position if location else 999,
                    dogs=sorted(group_dogs, key=lambda item: item.name.casefold()),
                )
            )
        result.sort(
            key=lambda item: (
                item.code == "NO-HOUSING",
                item.zone,
                item.row,
                item.position,
            )
        )
        return result

    @staticmethod
    def _pair_label(item: WorkParticipation) -> str | None:
        if item.actual_team_sequence is None:
            return None
        if item.assigned_role == "lead":
            return "Lead"
        if item.assigned_role == "wheel":
            return "Wheel"
        return f"Team {item.pair_index}"

    @staticmethod
    def _availability_label(availability: str | None) -> str:
        labels = {
            AvailabilityState.INJURED.value: "Injured",
            AvailabilityState.REST.value: "Rest",
            AvailabilityState.RESTRICTED.value: "Restricted",
            AvailabilityState.RETIRED.value: "Retired",
        }
        return labels.get(availability or "", "Not available")
