from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import Select, func, select
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
    HousingAssignment,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
)
from app.models.enums import (
    AvailabilityState,
    DogClass,
    LifecycleState,
    PlannedActivityType,
)
from app.schemas.daily_plans import (
    ActivityWrite,
    DailyPlanRead,
    EligibilityRead,
    EligibleDogRead,
    PlannedActivityRead,
    PlanParticipantRead,
)
from app.services.effective_state import EffectiveDogState


class DailyPlanError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DailyPlanService:
    """Date-scoped planning mutations built on canonical effective dog state."""

    def __init__(self, session: Session, clock: DemoClock) -> None:
        self.session = session
        self.clock = clock

    def read(self, plan_date: date) -> DailyPlanRead:
        self.validate_date(plan_date)
        return self._read(self._plan(plan_date), plan_date)

    def update_notes(
        self, plan_date: date, notes: str | None, expected_revision: int | None
    ) -> DailyPlanRead:
        self.validate_date(plan_date)
        plan = self._plan(plan_date, for_update=True)
        if plan is None:
            if notes is None:
                return self._read(None, plan_date)
            plan = DailyPlan(plan_date=plan_date, notes=notes, revision=1)
            self.session.add(plan)
        else:
            self._check_revision(plan, expected_revision)
            plan.notes = notes
            self._touch(plan)
            if notes is None and not plan.activities:
                self.session.delete(plan)
                self.session.flush()
                return self._read(None, plan_date)
        return self._refresh(plan_date)

    def create_activity(self, plan_date: date, payload: ActivityWrite) -> DailyPlanRead:
        self.validate_date(plan_date)
        plan = self._plan(plan_date, for_update=True)
        if plan is None:
            if payload.expected_revision is not None:
                raise DailyPlanError(
                    "plan_changed",
                    "This day changed. Reload it before saving.",
                    409,
                )
            plan = DailyPlan(plan_date=plan_date, revision=1)
            self.session.add(plan)
            self.session.flush()
        else:
            self._check_revision(plan, payload.expected_revision)
            self._touch(plan)

        dogs = self._validate_participants(plan_date, payload)
        sequence = (
            max((activity.sequence for activity in plan.activities), default=0) + 1
        )
        activity = PlannedActivity(
            daily_plan_id=plan.id,
            activity_type=payload.activity_type.value,
            sequence=sequence,
            start_time=payload.start_time,
            title=payload.title,
            distance_km=payload.distance_km,
            notes=payload.notes,
        )
        activity.participants = [
            PlannedActivityParticipant(dog_id=dog.id) for dog in dogs
        ]
        self.session.add(activity)
        return self._refresh(plan_date)

    def update_activity(
        self, plan_date: date, activity_id: UUID, payload: ActivityWrite
    ) -> DailyPlanRead:
        self.validate_date(plan_date)
        plan = self._required_plan(plan_date)
        self._check_revision(plan, payload.expected_revision)
        activity = self._required_activity(plan, activity_id)
        lineup_affecting_change = (
            activity.activity_type != payload.activity_type.value
            or activity.distance_km != payload.distance_km
            or {participant.dog.public_id for participant in activity.participants}
            != set(payload.participant_ids)
        )
        if activity.teams and lineup_affecting_change:
            if not payload.clear_saved_teams:
                raise DailyPlanError(
                    "saved_teams_require_clear",
                    "Changing the distance or participant pool will clear the "
                    "saved team lineup.",
                    409,
                )
            activity.teams.clear()
            self.session.flush()
        dogs = self._validate_participants(
            plan_date, payload, exclude_activity_id=activity.id
        )
        activity.activity_type = payload.activity_type.value
        activity.start_time = payload.start_time
        activity.title = payload.title
        activity.distance_km = payload.distance_km
        activity.notes = payload.notes
        existing_by_dog_id = {
            participant.dog_id: participant for participant in activity.participants
        }
        activity.participants = [
            existing_by_dog_id.get(dog.id) or PlannedActivityParticipant(dog_id=dog.id)
            for dog in dogs
        ]
        self._touch(plan)
        return self._refresh(plan_date)

    def move_activity(
        self,
        plan_date: date,
        activity_id: UUID,
        direction: str,
        expected_revision: int,
    ) -> DailyPlanRead:
        self.validate_date(plan_date)
        plan = self._required_plan(plan_date)
        self._check_revision(plan, expected_revision)
        ordered = sorted(plan.activities, key=lambda item: item.sequence)
        activity = self._required_activity(plan, activity_id)
        index = ordered.index(activity)
        target = index - 1 if direction == "up" else index + 1
        if target < 0 or target >= len(ordered):
            return self._read(plan, plan_date)
        ordered[index], ordered[target] = ordered[target], ordered[index]
        for sequence, item in enumerate(ordered, start=1):
            item.sequence = sequence
        self._touch(plan)
        return self._refresh(plan_date)

    def delete_activity(
        self, plan_date: date, activity_id: UUID, expected_revision: int
    ) -> DailyPlanRead:
        self.validate_date(plan_date)
        plan = self._required_plan(plan_date)
        self._check_revision(plan, expected_revision)
        activity = self._required_activity(plan, activity_id)
        plan.activities.remove(activity)
        self.session.delete(activity)
        if not plan.activities and plan.notes is None:
            self.session.delete(plan)
            self.session.flush()
            return self._read(None, plan_date)
        for sequence, item in enumerate(
            sorted(plan.activities, key=lambda row: row.sequence), start=1
        ):
            item.sequence = sequence
        self._touch(plan)
        return self._refresh(plan_date)

    def eligibility(
        self,
        plan_date: date,
        activity_type: PlannedActivityType,
        distance_km: int | None,
        *,
        exclude_activity_id: UUID | None = None,
    ) -> EligibilityRead:
        self.validate_date(plan_date)
        self._validate_activity_distance(activity_type, distance_km)
        excluded_internal_id: int | None = None
        if exclude_activity_id is not None:
            excluded = self.session.scalar(
                select(PlannedActivity).where(
                    PlannedActivity.public_id == exclude_activity_id
                )
            )
            if excluded is None or excluded.daily_plan.plan_date != plan_date:
                raise DailyPlanError("activity_not_found", "Activity not found.", 404)
            excluded_internal_id = excluded.id

        dogs = self._all_dogs()
        planned_km = self._planned_km(plan_date, excluded_internal_id)
        reads = [
            self._eligibility_read(
                dog, plan_date, activity_type, distance_km, planned_km.get(dog.id, 0)
            )
            for dog in dogs
        ]
        reads.sort(key=lambda item: (not item.eligible, item.name.casefold()))
        return EligibilityRead(
            selected_date=plan_date,
            activity_type=activity_type,
            distance_km=distance_km,
            max_daily_training_km=MAX_DAILY_DOG_DISTANCE_KM,
            dogs=reads,
        )

    def validate_date(self, plan_date: date) -> None:
        if not self.clock.season_start <= plan_date <= self.clock.season_end:
            raise DailyPlanError(
                "date_out_of_range",
                "Plan date must be within the demo season "
                f"{self.clock.season_start.isoformat()} through "
                f"{self.clock.season_end.isoformat()}.",
            )

    def _plan_query(self) -> Select[tuple[DailyPlan]]:
        participant_dogs = (
            selectinload(DailyPlan.activities)
            .selectinload(PlannedActivity.participants)
            .selectinload(PlannedActivityParticipant.dog)
        )
        return select(DailyPlan).options(
            selectinload(DailyPlan.activities),
            selectinload(DailyPlan.activities)
            .selectinload(PlannedActivity.teams)
            .selectinload(PlannedTeam.slots)
            .selectinload(PlannedTeamSlot.dog),
            participant_dogs.selectinload(Dog.class_periods),
            participant_dogs.selectinload(Dog.lifecycle_periods),
            participant_dogs.selectinload(Dog.availability_periods),
            participant_dogs.selectinload(Dog.role_capabilities),
            participant_dogs.selectinload(Dog.housing_assignments).selectinload(
                HousingAssignment.location
            ),
        )

    def _plan(self, plan_date: date, *, for_update: bool = False) -> DailyPlan | None:
        statement = self._plan_query().where(DailyPlan.plan_date == plan_date)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def _required_plan(self, plan_date: date) -> DailyPlan:
        plan = self._plan(plan_date, for_update=True)
        if plan is None:
            raise DailyPlanError("plan_not_found", "No plan exists for this date.", 404)
        return plan

    @staticmethod
    def _required_activity(plan: DailyPlan, activity_id: UUID) -> PlannedActivity:
        activity = next(
            (item for item in plan.activities if item.public_id == activity_id), None
        )
        if activity is None:
            raise DailyPlanError("activity_not_found", "Activity not found.", 404)
        return activity

    @staticmethod
    def _check_revision(plan: DailyPlan, expected_revision: int | None) -> None:
        if expected_revision != plan.revision:
            raise DailyPlanError(
                "plan_changed",
                "This day changed. Reload it before saving.",
                409,
            )

    @staticmethod
    def _touch(plan: DailyPlan) -> None:
        plan.revision += 1
        plan.updated_at = datetime.now(UTC)

    def _refresh(self, plan_date: date) -> DailyPlanRead:
        self.session.flush()
        self.session.expire_all()
        return self._read(self._plan(plan_date), plan_date)

    def _read(self, plan: DailyPlan | None, plan_date: date) -> DailyPlanRead:
        state = EffectiveDogState(plan_date)
        activities: list[PlannedActivityRead] = []
        if plan is not None:
            for activity in sorted(plan.activities, key=lambda item: item.sequence):
                participants = []
                for participant in sorted(
                    activity.participants, key=lambda item: item.dog.name.casefold()
                ):
                    dog = participant.dog
                    housing = state.housing(dog)
                    dog_class, _ = state.dog_class(dog)
                    participants.append(
                        PlanParticipantRead(
                            id=dog.public_id,
                            name=dog.name,
                            housing_code=(housing.location.code if housing else None),
                            dog_class=dog_class,
                            availability=state.availability(dog),
                        )
                    )
                activities.append(
                    PlannedActivityRead(
                        id=activity.public_id,
                        activity_type=PlannedActivityType(activity.activity_type),
                        sequence=activity.sequence,
                        start_time=activity.start_time,
                        title=activity.title,
                        distance_km=activity.distance_km,
                        notes=activity.notes,
                        participants=participants,
                        team_count=len(activity.teams),
                        arranged_dog_count=sum(
                            len(team.slots) for team in activity.teams
                        ),
                    )
                )
        return DailyPlanRead(
            selected_date=plan_date,
            season_start=self.clock.season_start,
            season_end=self.clock.season_end,
            reference_date=self.clock.reference_date,
            exists=plan is not None,
            id=plan.public_id if plan else None,
            revision=plan.revision if plan else None,
            notes=plan.notes if plan else None,
            activities=activities,
        )

    def _all_dogs(self) -> list[Dog]:
        return list(
            self.session.scalars(
                select(Dog).options(
                    selectinload(Dog.class_periods),
                    selectinload(Dog.lifecycle_periods),
                    selectinload(Dog.availability_periods),
                    selectinload(Dog.housing_assignments).selectinload(
                        HousingAssignment.location
                    ),
                )
            ).unique()
        )

    def _validate_participants(
        self,
        plan_date: date,
        payload: ActivityWrite,
        *,
        exclude_activity_id: int | None = None,
    ) -> list[Dog]:
        self._validate_activity_distance(payload.activity_type, payload.distance_km)
        dogs_by_public_id = {dog.public_id: dog for dog in self._all_dogs()}
        missing = [
            dog_id
            for dog_id in payload.participant_ids
            if dog_id not in dogs_by_public_id
        ]
        if missing:
            raise DailyPlanError(
                "participant_not_found", "One or more selected dogs do not exist."
            )
        planned_km = self._planned_km(plan_date, exclude_activity_id)
        dogs = [dogs_by_public_id[dog_id] for dog_id in payload.participant_ids]
        for dog in dogs:
            read = self._eligibility_read(
                dog,
                plan_date,
                payload.activity_type,
                payload.distance_km,
                planned_km.get(dog.id, 0),
            )
            if not read.eligible:
                raise DailyPlanError(
                    "dog_not_eligible",
                    f"{dog.name} cannot join this activity: {read.reasons[0]}.",
                )
        return dogs

    @staticmethod
    def _validate_activity_distance(
        activity_type: PlannedActivityType, distance_km: int | None
    ) -> None:
        if activity_type is PlannedActivityType.TRAINING and distance_km not in {5, 10}:
            raise DailyPlanError(
                "unsupported_distance", "Training distance must be 5 km or 10 km."
            )
        if (
            activity_type is not PlannedActivityType.TRAINING
            and distance_km is not None
        ):
            raise DailyPlanError(
                "unexpected_distance", "Only Training activities have sled distance."
            )

    def _planned_km(
        self, plan_date: date, exclude_activity_id: int | None
    ) -> dict[int, int]:
        statement = (
            select(
                PlannedActivityParticipant.dog_id,
                func.sum(PlannedActivity.distance_km),
            )
            .join(PlannedActivity)
            .join(DailyPlan)
            .where(
                DailyPlan.plan_date == plan_date,
                PlannedActivity.activity_type == PlannedActivityType.TRAINING.value,
            )
            .group_by(PlannedActivityParticipant.dog_id)
        )
        if exclude_activity_id is not None:
            statement = statement.where(PlannedActivity.id != exclude_activity_id)
        return {
            dog_id: int(total or 0) for dog_id, total in self.session.execute(statement)
        }

    def _eligibility_read(
        self,
        dog: Dog,
        plan_date: date,
        activity_type: PlannedActivityType,
        distance_km: int | None,
        planned_training_km: int,
    ) -> EligibleDogRead:
        state = EffectiveDogState(plan_date)
        dog_class, _ = state.dog_class(dog)
        lifecycle = state.lifecycle(dog)
        availability = state.availability(dog)
        housing = state.housing(dog)
        reasons: list[str] = []

        if dog.birth_date > plan_date:
            reasons.append("Not yet born")
        elif lifecycle != LifecycleState.ACTIVE.value:
            reasons.append("Archived" if lifecycle == "archived" else "Not active")
        elif activity_type is not PlannedActivityType.REST:
            if availability != AvailabilityState.AVAILABLE.value:
                reasons.append(self._availability_label(availability))
            elif activity_type is PlannedActivityType.TRAINING:
                if dog_class == DogClass.PUPPY.value:
                    reasons.append("Puppy")
                elif dog_class == DogClass.JUNIOR.value:
                    reasons.append("Junior")
                elif dog_class == DogClass.TRAINING.value and distance_km == 10:
                    reasons.append("Training class · 5 km only")
                elif dog_class not in {
                    DogClass.TRAINING.value,
                    DogClass.STANDARD.value,
                }:
                    reasons.append("Not eligible for regular sled training")
                elif distance_km is not None:
                    try:
                        add_daily_dog_distance(planned_training_km, distance_km)
                    except WorkloadRuleViolation:
                        reasons.append("30 km daily limit reached")

        return EligibleDogRead(
            id=dog.public_id,
            name=dog.name,
            housing_code=housing.location.code if housing else None,
            dog_class=dog_class,
            availability=availability,
            eligible=not reasons,
            reasons=reasons,
            planned_training_km=planned_training_km,
        )

    @staticmethod
    def _availability_label(availability: str | None) -> str:
        labels = {
            AvailabilityState.INJURED.value: "Injured",
            AvailabilityState.REST.value: "Rest",
            AvailabilityState.RESTRICTED.value: "Restricted",
            AvailabilityState.RETIRED.value: "Retired",
        }
        return labels.get(availability or "", "Not available")
