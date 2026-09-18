from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.demo_clock import DemoClock
from app.domain.team_builder import (
    SUPPORTED_TEAM_SIZES,
    Candidate,
    GeneratedLineup,
    TeamBuilderSolveError,
    generate_lineup,
    recommended_configuration,
    validate_role_capability,
)
from app.models import (
    DailyPlan,
    Dog,
    DogRelationshipConstraint,
    HousingAssignment,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)
from app.models.enums import PlannedActivityType, RelationshipKind
from app.schemas.team_builder import (
    CapabilitySummaryRead,
    GeneratedTeamsRead,
    PlannedTeamRead,
    PlannedTeamWrite,
    SaveTeamsRequest,
    TeamBuilderActivityRead,
    TeamBuilderCandidateRead,
    TeamBuilderContextRead,
    TeamRelationshipRead,
    TeamSlotRead,
    UnassignedDogRead,
    WorkloadMetricsRead,
)
from app.services.daily_plan_service import DailyPlanService
from app.services.demo_workspace_service import scoped_date_filter


class TeamBuilderError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 422,
        details: dict[str, int] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class TeamBuilderService:
    """P6 projection, deterministic generation, and validated lineup persistence."""

    def __init__(
        self, session: Session, clock: DemoClock, workspace_id: int | None = None
    ) -> None:
        self.session = session
        self.clock = clock
        self.workspace_id = workspace_id
        self.plans = DailyPlanService(session, clock, workspace_id)

    def context(self, plan_date: date, activity_id: UUID) -> TeamBuilderContextRead:
        activity = self._required_activity(plan_date, activity_id)
        candidates, candidate_reads = self._candidates(activity, plan_date)
        relationships = self._relationships(activity)
        preferred, _ = self._relationship_sets(relationships)
        recommended_count, recommended_size = recommended_configuration(len(candidates))
        return TeamBuilderContextRead(
            activity=self._activity_read(activity, plan_date),
            recommended_team_count=recommended_count,
            recommended_team_size=recommended_size,
            supported_team_sizes=list(SUPPORTED_TEAM_SIZES),
            capability_summary=CapabilitySummaryRead(
                lead=sum("lead" in candidate.roles for candidate in candidates),
                team=sum("team" in candidate.roles for candidate in candidates),
                wheel=sum("wheel" in candidate.roles for candidate in candidates),
            ),
            candidates=candidate_reads,
            relationships=[self._relationship_read(item) for item in relationships],
            saved_teams=self._saved_teams(activity, candidates, preferred),
        )

    def generate(
        self,
        plan_date: date,
        activity_id: UUID,
        *,
        team_count: int,
        team_size: int,
    ) -> GeneratedTeamsRead:
        activity = self._required_activity(plan_date, activity_id)
        candidates, _ = self._candidates(activity, plan_date)
        relationships = self._relationships(activity)
        preferred, conflicts = self._relationship_sets(relationships)
        try:
            generated = generate_lineup(
                candidates,
                team_count=team_count,
                team_size=team_size,
                preferred_pairs=preferred,
                hard_conflicts=conflicts,
            )
        except TeamBuilderSolveError as error:
            raise TeamBuilderError(
                error.code, error.message, details=error.details
            ) from error
        by_id = {candidate.dog_id: candidate for candidate in candidates}
        return GeneratedTeamsRead(
            activity=self._activity_read(activity, plan_date),
            teams=self._generated_teams(generated, by_id),
            unassigned=[
                UnassignedDogRead(
                    dog_id=UUID(dog_id),
                    dog_name=by_id[dog_id].name,
                    reason=reason,
                )
                for dog_id, reason in generated.unassigned
            ],
        )

    def save(
        self,
        plan_date: date,
        activity_id: UUID,
        payload: SaveTeamsRequest,
    ) -> TeamBuilderContextRead:
        self.plans.validate_date(plan_date)
        self.plans.materialize(plan_date)
        plan = self.plans._required_plan(plan_date)  # shared revision lock boundary
        self.plans._check_revision(plan, payload.expected_revision)
        activity = self.plans._required_activity(plan, activity_id)
        if activity.activity_type != PlannedActivityType.TRAINING.value:
            raise TeamBuilderError(
                "training_required", "Teams can only be built for Training activities."
            )
        if activity.teams and not payload.replace_existing:
            raise TeamBuilderError(
                "saved_teams_require_replace",
                "Saved teams already exist. Confirm rebuild before replacing them.",
                409,
            )

        candidates, _ = self._candidates(activity, plan_date)
        relationships = self._relationships(activity)
        _, conflicts = self._relationship_sets(relationships)
        by_public_id = {UUID(item.dog_id): item for item in candidates}
        dogs_by_public_id = {
            participant.dog.public_id: participant.dog
            for participant in activity.participants
        }
        self._validate_saved_lineup(payload.teams, by_public_id, conflicts)

        activity.teams.clear()
        self.session.flush()
        for team_write in payload.teams:
            team = PlannedTeam(
                planned_activity_id=activity.id,
                sequence=team_write.sequence,
                team_size=team_write.team_size,
                display_label=team_write.display_label or f"Team {team_write.sequence}",
                updated_at=datetime.now(UTC),
            )
            team.slots = [
                PlannedTeamSlot(
                    planned_activity_id=activity.id,
                    dog_id=dogs_by_public_id[slot.dog_id].id,
                    pair_index=slot.pair_index,
                    side=slot.side,
                    harness_role=slot.harness_role,
                    position_order=slot.position_order,
                )
                for slot in team_write.slots
            ]
            activity.teams.append(team)
        self.plans._touch(plan)
        self.session.flush()
        self.session.expire_all()
        return self.context(plan_date, activity_id)

    def _required_activity(self, plan_date: date, activity_id: UUID) -> PlannedActivity:
        self.plans.validate_date(plan_date)
        participant_dog = selectinload(PlannedActivity.participants).selectinload(
            PlannedActivityParticipant.dog
        )
        statement = (
            select(PlannedActivity)
            .join(DailyPlan)
            .where(
                DailyPlan.plan_date == plan_date,
                scoped_date_filter(DailyPlan, self.workspace_id, DailyPlan.plan_date),
                PlannedActivity.public_id == activity_id,
            )
            .options(
                selectinload(PlannedActivity.daily_plan),
                participant_dog.selectinload(Dog.class_periods),
                participant_dog.selectinload(Dog.lifecycle_periods),
                participant_dog.selectinload(Dog.availability_periods),
                participant_dog.selectinload(Dog.role_capabilities),
                participant_dog.selectinload(Dog.housing_assignments).selectinload(
                    HousingAssignment.location
                ),
                selectinload(PlannedActivity.teams)
                .selectinload(PlannedTeam.slots)
                .selectinload(PlannedTeamSlot.dog),
            )
        )
        activity = self.session.scalar(statement)
        if activity is None:
            raise TeamBuilderError("activity_not_found", "Activity not found.", 404)
        if activity.activity_type != PlannedActivityType.TRAINING.value:
            raise TeamBuilderError(
                "training_required", "Teams can only be built for Training activities."
            )
        return activity

    def _candidates(
        self, activity: PlannedActivity, plan_date: date
    ) -> tuple[list[Candidate], list[TeamBuilderCandidateRead]]:
        eligibility = self.plans.eligibility(
            plan_date,
            PlannedActivityType.TRAINING,
            activity.distance_km,
            exclude_activity_id=activity.public_id,
        )
        eligibility_by_id = {item.id: item for item in eligibility.dogs}
        dog_ids = [participant.dog_id for participant in activity.participants]
        workload = self._workload(dog_ids, plan_date)
        planned_km = self.plans._planned_km(plan_date, None)
        candidates: list[Candidate] = []
        reads: list[TeamBuilderCandidateRead] = []
        for participant in sorted(
            activity.participants, key=lambda item: item.dog.name.casefold()
        ):
            dog = participant.dog
            eligible = eligibility_by_id[dog.public_id]
            metrics = workload.get(dog.id, (0, 0, 0, 0, None))
            roles = frozenset(item.role for item in dog.role_capabilities)
            candidate = Candidate(
                dog_id=str(dog.public_id),
                name=dog.name,
                roles=roles,
                housing_code=eligible.housing_code,
                km_7d=metrics[0],
                km_14d=metrics[1],
                season_km=metrics[2],
                starts_14d=metrics[3],
                days_since_work=metrics[4],
                planned_km=planned_km.get(dog.id, 0),
            )
            reads.append(
                TeamBuilderCandidateRead(
                    id=dog.public_id,
                    name=dog.name,
                    housing_code=eligible.housing_code,
                    dog_class=eligible.dog_class,
                    availability=eligible.availability,
                    capabilities=sorted(roles),
                    eligible=eligible.eligible,
                    reasons=eligible.reasons,
                    workload=WorkloadMetricsRead(
                        km_7d=candidate.km_7d,
                        km_14d=candidate.km_14d,
                        season_km=candidate.season_km,
                        starts_14d=candidate.starts_14d,
                        days_since_last_work=candidate.days_since_work,
                        planned_km_today=candidate.planned_km,
                    ),
                )
            )
            if eligible.eligible:
                candidates.append(candidate)
        return candidates, reads

    def _workload(
        self, dog_ids: list[int], plan_date: date
    ) -> dict[int, tuple[int, int, int, int, int | None]]:
        if not dog_ids:
            return {}
        start_7d = plan_date - timedelta(days=7)
        start_14d = plan_date - timedelta(days=14)
        statement = (
            select(
                WorkParticipation.dog_id,
                func.sum(
                    case(
                        (WorkSession.work_date >= start_7d, WorkSession.distance_km),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (WorkSession.work_date >= start_14d, WorkSession.distance_km),
                        else_=0,
                    )
                ),
                func.sum(WorkSession.distance_km),
                func.sum(case((WorkSession.work_date >= start_14d, 1), else_=0)),
                func.max(WorkSession.work_date),
            )
            .join(WorkSession)
            .where(
                WorkParticipation.dog_id.in_(dog_ids),
                WorkSession.work_date >= self.clock.season_start,
                WorkSession.work_date < plan_date,
                scoped_date_filter(
                    WorkSession, self.workspace_id, WorkSession.work_date
                ),
            )
            .group_by(WorkParticipation.dog_id)
        )
        result: dict[int, tuple[int, int, int, int, int | None]] = {}
        rows = self.session.execute(statement)
        for dog_id, km_7d, km_14d, season_km, starts_14d, last_work in rows:
            result[dog_id] = (
                int(km_7d or 0),
                int(km_14d or 0),
                int(season_km or 0),
                int(starts_14d or 0),
                (plan_date - last_work).days if last_work else None,
            )
        return result

    def _relationships(
        self, activity: PlannedActivity
    ) -> list[DogRelationshipConstraint]:
        dog_ids = [participant.dog_id for participant in activity.participants]
        if not dog_ids:
            return []
        return list(
            self.session.scalars(
                select(DogRelationshipConstraint)
                .where(
                    DogRelationshipConstraint.dog_a_id.in_(dog_ids),
                    DogRelationshipConstraint.dog_b_id.in_(dog_ids),
                )
                .options(
                    selectinload(DogRelationshipConstraint.dog_a),
                    selectinload(DogRelationshipConstraint.dog_b),
                )
                .order_by(DogRelationshipConstraint.id)
            )
        )

    @staticmethod
    def _relationship_sets(
        relationships: list[DogRelationshipConstraint],
    ) -> tuple[set[frozenset[str]], set[frozenset[str]]]:
        preferred: set[frozenset[str]] = set()
        conflicts: set[frozenset[str]] = set()
        for item in relationships:
            pair = frozenset((str(item.dog_a.public_id), str(item.dog_b.public_id)))
            if item.relationship_kind == RelationshipKind.PREFERRED_PAIR.value:
                preferred.add(pair)
            else:
                conflicts.add(pair)
        return preferred, conflicts

    @staticmethod
    def _relationship_read(item: DogRelationshipConstraint) -> TeamRelationshipRead:
        return TeamRelationshipRead(
            dog_a_id=item.dog_a.public_id,
            dog_b_id=item.dog_b.public_id,
            kind=item.relationship_kind,
        )

    @staticmethod
    def _activity_read(
        activity: PlannedActivity, plan_date: date
    ) -> TeamBuilderActivityRead:
        assert activity.distance_km is not None
        return TeamBuilderActivityRead(
            id=activity.public_id,
            date=plan_date,
            title=activity.title,
            distance_km=activity.distance_km,
            participant_count=len(activity.participants),
            plan_revision=activity.daily_plan.revision,
        )

    def _saved_teams(
        self,
        activity: PlannedActivity,
        candidates: list[Candidate],
        preferred: set[frozenset[str]],
    ) -> list[PlannedTeamRead]:
        by_id = {candidate.dog_id: candidate for candidate in candidates}
        result: list[PlannedTeamRead] = []
        for team in sorted(activity.teams, key=lambda item: item.sequence):
            slots: list[TeamSlotRead] = []
            by_pair: dict[int, list[PlannedTeamSlot]] = defaultdict(list)
            for slot in team.slots:
                by_pair[slot.pair_index].append(slot)
            for pair_index in sorted(by_pair):
                pair = sorted(by_pair[pair_index], key=lambda item: item.side)
                pair_key = frozenset(str(item.dog.public_id) for item in pair)
                pair_reasons: list[str] = []
                if pair_key in preferred:
                    pair_reasons.append("Preferred pair")
                housing = [by_id.get(str(item.dog.public_id)) for item in pair]
                first_candidate = housing[0] if len(housing) == 2 else None
                second_candidate = housing[1] if len(housing) == 2 else None
                if (
                    first_candidate is not None
                    and second_candidate is not None
                    and first_candidate.housing_code
                    and first_candidate.housing_code == second_candidate.housing_code
                ):
                    pair_reasons.append("Home pair")
                for slot in pair:
                    slots.append(
                        self._slot_read(
                            slot.dog.public_id,
                            slot.dog.name,
                            slot.pair_index,
                            slot.side,
                            slot.harness_role,
                            slot.position_order,
                            [f"{slot.harness_role.title()} capable", *pair_reasons],
                            team.team_size,
                        )
                    )
            result.append(
                PlannedTeamRead(
                    id=team.public_id,
                    sequence=team.sequence,
                    display_label=team.display_label or f"Team {team.sequence}",
                    team_size=team.team_size,
                    slots=sorted(slots, key=lambda item: item.position_order),
                )
            )
        return result

    def _generated_teams(
        self, generated: GeneratedLineup, by_id: dict[str, Candidate]
    ) -> list[PlannedTeamRead]:
        teams = []
        for team_index in range(generated.team_count):
            slots = []
            team_slots = [
                item for item in generated.slots if item.team_index == team_index
            ]
            for slot in team_slots:
                candidate = by_id[slot.dog_id]
                position_order = slot.pair_index * 2 + (1 if slot.side == "left" else 2)
                slots.append(
                    self._slot_read(
                        UUID(slot.dog_id),
                        candidate.name,
                        slot.pair_index,
                        slot.side,
                        slot.role,
                        position_order,
                        list(slot.explanations),
                        generated.team_size,
                    )
                )
            teams.append(
                PlannedTeamRead(
                    sequence=team_index + 1,
                    display_label=f"Team {team_index + 1}",
                    team_size=generated.team_size,
                    slots=sorted(slots, key=lambda item: item.position_order),
                )
            )
        return teams

    @staticmethod
    def _slot_read(
        dog_id: UUID,
        dog_name: str,
        pair_index: int,
        side: str,
        role: str,
        position_order: int,
        explanations: list[str],
        team_size: int,
    ) -> TeamSlotRead:
        pair_count = team_size // 2
        pair_label = (
            "Lead"
            if pair_index == 0
            else "Wheel"
            if pair_index == pair_count - 1
            else f"Team {pair_index}"
        )
        return TeamSlotRead(
            dog_id=dog_id,
            dog_name=dog_name,
            pair_index=pair_index,
            pair_label=pair_label,
            side=side,
            harness_role=role,
            position_order=position_order,
            explanations=explanations,
        )

    def _validate_saved_lineup(
        self,
        teams: list[PlannedTeamWrite],
        candidates: dict[UUID, Candidate],
        conflicts: set[frozenset[str]],
    ) -> None:
        sizes = {team.team_size for team in teams}
        if len(sizes) != 1 or next(iter(sizes)) not in SUPPORTED_TEAM_SIZES:
            raise TeamBuilderError(
                "invalid_team_size", "All teams must use one supported even team size."
            )
        used: set[UUID] = set()
        for team in teams:
            expected = {
                (pair_index, side): (
                    "lead"
                    if pair_index == 0
                    else "wheel"
                    if pair_index == team.team_size // 2 - 1
                    else "team"
                )
                for pair_index in range(team.team_size // 2)
                for side in ("left", "right")
            }
            actual = {(slot.pair_index, slot.side): slot for slot in team.slots}
            if set(actual) != set(expected):
                raise TeamBuilderError(
                    "invalid_geometry",
                    "Every Left and Right harness slot must be filled.",
                )
            expected_order = {
                (pair_index, side): pair_index * 2 + (1 if side == "left" else 2)
                for pair_index, side in expected
            }
            if any(
                actual[position].position_order != expected_order[position]
                for position in expected
            ):
                raise TeamBuilderError(
                    "invalid_geometry",
                    "Harness position order must match pair and side geometry.",
                )
            for position, role in expected.items():
                slot = actual[position]
                if slot.harness_role != role:
                    raise TeamBuilderError(
                        "invalid_geometry",
                        "Harness roles do not match the team geometry.",
                    )
                candidate = candidates.get(slot.dog_id)
                if candidate is None:
                    raise TeamBuilderError(
                        "dog_not_eligible",
                        "Every saved dog must remain an eligible selected participant.",
                    )
                if slot.dog_id in used:
                    raise TeamBuilderError(
                        "duplicate_dog",
                        "A dog may occupy only one slot in this activity.",
                    )
                try:
                    validate_role_capability(candidate, role)
                except TeamBuilderSolveError as error:
                    raise TeamBuilderError(error.code, error.message) from error
                used.add(slot.dog_id)
            for pair_index in range(team.team_size // 2):
                pair = frozenset(
                    str(actual[(pair_index, side)].dog_id) for side in ("left", "right")
                )
                if pair in conflicts:
                    left = candidates[actual[(pair_index, "left")].dog_id].name
                    right = candidates[actual[(pair_index, "right")].dog_id].name
                    raise TeamBuilderError(
                        "hard_pair_conflict", f"Cannot pair {left} with {right}."
                    )
