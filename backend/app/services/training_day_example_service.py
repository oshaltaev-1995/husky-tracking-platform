from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.domain.team_builder import TeamBuilderSolveError, generate_lineup
from app.models import DemoWorkspace, WorkSession
from app.models.enums import PlannedActivityType
from app.schemas.daily_plans import ActivityWrite, DailyPlanRead
from app.schemas.training_day_example import (
    TrainingDayApply,
    TrainingDayParticipantRead,
    TrainingDayProposal,
    TrainingDayWindowRead,
)
from app.services.daily_plan_service import DailyPlanError, DailyPlanService
from app.services.demo_workspace_service import (
    DemoWorkspaceExpiredError,
    scoped_date_filter,
)
from app.services.housing_context import lock_workspace
from app.services.team_builder_service import TeamBuilderService

TRAINING_DAY_DATE = date(2026, 3, 29)
PRESET_VERSION = "training-day-v1"
WINDOWS = ((9, 0, 10, 0), (10, 30, 11, 30), (12, 30, 13, 30), (14, 0, 15, 0))


class TrainingDayExampleService:
    """One opt-in example, never a seeded day or a second plan/actual model."""

    def __init__(self, session: Session, clock: DemoClock, workspace_id: int) -> None:
        self.session = session
        self.clock = clock
        self.workspace_id = workspace_id
        self.plans = DailyPlanService(session, clock, workspace_id)
        self.builder = TeamBuilderService(session, clock, workspace_id)

    @staticmethod
    def windows() -> list[TrainingDayWindowRead]:
        result = []
        for sequence, (sh, sm, eh, em) in enumerate(WINDOWS, 1):
            start, end = time(sh, sm), time(eh, em)
            result.append(
                TrainingDayWindowRead(
                    sequence=sequence,
                    start_time=start,
                    suggested_end_time=end,
                    title=(
                        f"Group {sequence} · 5 km Training Loop · "
                        f"{start:%H:%M}–{end:%H:%M}"
                    ),
                )
            )
        return result

    def _workspace(self) -> DemoWorkspace:
        workspace = lock_workspace(self.session, self.workspace_id)
        if workspace is None:
            raise DemoWorkspaceExpiredError(
                "Your demo session expired. Reload the demo before "
                "reviewing this example."
            )
        return workspace

    def _occupied(self) -> bool:
        return (
            self.plans._plan(TRAINING_DAY_DATE) is not None
            or self.session.scalar(
                select(WorkSession.id)
                .where(
                    WorkSession.work_date == TRAINING_DAY_DATE,
                    scoped_date_filter(
                        WorkSession, self.workspace_id, WorkSession.work_date
                    ),
                )
                .limit(1)
            )
            is not None
        )

    def _pool(self) -> list[TrainingDayParticipantRead]:
        dogs = self.plans._all_dogs()
        candidates, reads = self.builder.candidates_for_pool(TRAINING_DAY_DATE, 5, dogs)
        eligible_ids = {UUID(candidate.dog_id) for candidate in candidates}
        relationships = self.builder.relationships_for_dogs(
            [dog.id for dog in dogs if dog.public_id in eligible_ids]
        )
        preferred, conflicts = self.builder._relationship_sets(relationships)
        # Reuse P6 selection/role/pair search and strictly-before-date actual workload.
        # Only the selected pool is retained; the solver's teams are NOT persisted.
        generated = generate_lineup(
            candidates,
            team_count=2,
            team_size=8,
            preferred_pairs=preferred,
            hard_conflicts=conflicts,
        )
        selected = {UUID(slot.dog_id) for slot in generated.slots}
        return [
            TrainingDayParticipantRead(
                id=dog.id,
                name=dog.name,
                housing_code=dog.housing_code,
                dog_class=dog.dog_class,
                availability=dog.availability,
                capabilities=dog.capabilities,
            )
            for dog in reads
            if dog.id in selected
        ]

    @staticmethod
    def _precondition(workspace: DemoWorkspace, ids: list[UUID], when: date) -> str:
        # Purpose-separated from housing-move authorization. Reset advances the
        # existing generation even if the workspace/day was already empty.
        message = json.dumps(
            {
                "purpose": "training-day-example-apply",
                "version": PRESET_VERSION,
                "workspace": str(workspace.public_id),
                "generation": workspace.housing_revision,
                "date": when.isoformat(),
                "participants": sorted(str(item) for item in ids),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        signature = hmac.new(
            get_settings().demo_session_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"td1{signature}"

    def preview(self) -> TrainingDayProposal:
        workspace = self._workspace()
        self.plans.validate_date(TRAINING_DAY_DATE)
        reason = None
        pool: list[TrainingDayParticipantRead] = []
        if self._occupied():
            reason = (
                "29 March already has a Daily Plan or actual work. "
                "Open that day to review it; the example will not replace anything."
            )
        else:
            try:
                pool = self._pool()
            except TeamBuilderSolveError as error:
                reason = (
                    "This example needs sixteen eligible dogs that can form "
                    f"two 8-dog teams. {error.message}"
                )
        return TrainingDayProposal(
            date=TRAINING_DAY_DATE,
            available=reason is None,
            unavailable_reason=reason,
            activities=self.windows(),
            participants=pool,
            unique_dogs=len(pool),
            planned_participations=len(pool) * 4,
            planned_dog_km=len(pool) * 20,
            planned_km_per_dog=20,
            precondition=self._precondition(
                workspace, [dog.id for dog in pool], TRAINING_DAY_DATE
            )
            if reason is None
            else None,
        )

    def apply(self, payload: TrainingDayApply) -> DailyPlanRead:
        workspace = self._workspace()
        if payload.date != TRAINING_DAY_DATE or not hmac.compare_digest(
            payload.precondition.encode(),
            self._precondition(
                workspace, payload.participant_ids, payload.date
            ).encode(),
        ):
            raise DailyPlanError(
                "training_day_changed",
                "This review is no longer current. Reload the day and "
                "review a new proposal.",
                409,
            )
        if self._occupied():
            raise DailyPlanError(
                "training_day_occupied",
                "29 March already has a plan or actual work. Nothing was replaced. "
                "Open the current day.",
                409,
            )
        try:
            pool = self._pool()
        except TeamBuilderSolveError as error:
            raise DailyPlanError(
                "training_day_changed",
                "The reviewed dogs can no longer form this example. "
                "Review a new proposal.",
                409,
            ) from error
        if {dog.id for dog in pool} != set(payload.participant_ids):
            raise DailyPlanError(
                "training_day_changed",
                "The reviewed dog pool changed. Review a new proposal; "
                "no dogs were substituted.",
                409,
            )
        revision = None
        result: DailyPlanRead | None = None
        for window in self.windows():
            # Existing writes flush only. The caller owns ONE transaction around
            # all four writes, including materialization and every validation.
            result = self.plans.create_activity(
                TRAINING_DAY_DATE,
                ActivityWrite(
                    activity_type=PlannedActivityType.TRAINING,
                    start_time=window.start_time,
                    title=window.title,
                    distance_km=5,
                    notes=(
                        "Suggested example schedule. The same 16 dogs take part "
                        "in four 5 km Training Loops (20 planned km each). Arrange "
                        "and save teams separately; actual work requires its own "
                        "confirmation."
                    ),
                    participant_ids=payload.participant_ids,
                    expected_revision=revision,
                ),
            )
            revision = result.revision
        assert result is not None
        return result
