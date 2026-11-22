from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from time import monotonic
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg import Error as PsycopgError
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import Session, sessionmaker

from app.core.demo_clock import DemoClock
from app.domain.team_builder import Candidate
from app.models import DailyPlan, Dog, PlannedActivity, WorkSession
from app.models.enums import PlannedActivityType
from app.operations.checks import evaluate
from app.operations.schemas import (
    Activity,
    Actual,
    DogState,
    Eligibility,
    Entity,
    Location,
    OperationError,
    Role,
    SavedSlot,
    SavedTeam,
    Snapshot,
)
from app.schemas.team_builder import PlannedTeamWrite, TeamSlotWrite
from app.services.daily_entry_service import DailyEntryService
from app.services.daily_plan_service import DailyPlanService
from app.services.demo_workspace_service import resolve_workspace, scoped_date_filter
from app.services.effective_state import EffectiveDogState
from app.services.housing_context import load_housing_context, lock_workspace
from app.services.kennel_map_read_service import KennelMapReadService
from app.services.team_builder_service import TeamBuilderError, TeamBuilderService


@dataclass(frozen=True, slots=True)
class _Binding:
    workspace_id: int
    identity: UUID
    expires_at: datetime
    reset_generation: int


@dataclass(frozen=True, slots=True)
class RunContext:
    snapshot: Snapshot
    _binding: _Binding = field(repr=False)


class SnapshotReader:
    """Own short transaction/session; never give an ORM/session/lock to a provider."""

    def __init__(self, sessions: sessionmaker[Session], clock: DemoClock, secret: str):
        self._sessions, self.clock, self._secret = sessions, clock, secret

    @staticmethod
    def _checkpoint(
        deadline: float | None, cancelled: Callable[[], bool] | None
    ) -> int:
        if cancelled is not None and cancelled():
            raise OperationError("cancelled")
        remaining = 8.0 if deadline is None else deadline - monotonic()
        if remaining <= 0:
            raise OperationError("timeout")
        return max(1, min(8000, int(remaining * 1000)))

    @contextmanager
    def _read_session(
        self, deadline: float | None, cancelled: Callable[[], bool] | None
    ) -> Iterator[Session]:
        self._checkpoint(deadline, cancelled)
        try:
            with self._sessions() as session, session.begin(), session.no_autoflush:
                connection = session.connection()

                def before_query(
                    _: Connection,
                    cursor: Any,
                    statement: str,
                    parameters: Any,
                    context: Any,
                    executemany: bool,
                ) -> None:
                    milliseconds = self._checkpoint(deadline, cancelled)
                    # Transaction-local driver settings, never domain writes. Reapply
                    # each query so a late query cannot inherit an earlier long wait.
                    cursor.execute(f"SET LOCAL statement_timeout = '{milliseconds}ms'")
                    cursor.execute(
                        f"SET LOCAL lock_timeout = '{min(5000, milliseconds)}ms'"
                    )

                event.listen(connection, "before_cursor_execute", before_query)
                try:
                    yield session
                    self._checkpoint(deadline, cancelled)
                finally:
                    event.remove(connection, "before_cursor_execute", before_query)
        except PoolTimeout:
            raise OperationError("timeout") from None
        except (DBAPIError, PsycopgError) as error:
            if cancelled is not None and cancelled():
                raise OperationError("cancelled") from None
            code = getattr(getattr(error, "orig", error), "sqlstate", None)
            raise OperationError(
                "timeout" if code in {"57014", "55P03"} else "database_unavailable"
            ) from None

    def capture(
        self,
        cookie: str | None,
        selected_date: date,
        *,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> RunContext:
        if (
            type(selected_date) is not date
            or not self.clock.season_start <= selected_date <= self.clock.season_end
        ):
            raise OperationError("date_out_of_range")
        if not cookie:
            raise OperationError("session_required")
        with self._read_session(deadline, cancelled) as session:
            workspace = resolve_workspace(session, cookie, self._secret)
            if workspace is None:
                raise OperationError("session_expired")
            workspace = lock_workspace(session, workspace.id)
            if workspace is None:
                raise OperationError("session_expired")
            # Every public writer takes this same row first; cleanup/Reset wait too.
            binding = _Binding(
                workspace.id,
                workspace.public_id,
                workspace.expires_at,
                workspace.housing_revision,
            )
            housing = load_housing_context(session, self.clock, workspace.id)
            if housing.workspace_id != workspace.id:
                raise OperationError("session_expired")
            # Reject oversized inputs BEFORE eager-loading a potentially large graph.
            activity_count = (
                session.scalar(
                    select(func.count())
                    .select_from(PlannedActivity)
                    .join(DailyPlan)
                    .where(
                        DailyPlan.plan_date == selected_date,
                        scoped_date_filter(
                            DailyPlan, workspace.id, DailyPlan.plan_date
                        ),
                    )
                )
                or 0
            )
            actual_count = (
                session.scalar(
                    select(func.count())
                    .select_from(WorkSession)
                    .where(
                        WorkSession.work_date == selected_date,
                        scoped_date_filter(
                            WorkSession, workspace.id, WorkSession.work_date
                        ),
                    )
                )
                or 0
            )
            dog_count = session.scalar(select(func.count()).select_from(Dog)) or 0
            if activity_count > 32 or actual_count > 64 or dog_count > 60:
                raise OperationError("snapshot_too_large")
            plans = DailyPlanService(
                session, self.clock, workspace.id, housing_context=housing
            )
            builder = TeamBuilderService(
                session, self.clock, workspace.id, housing_context=housing
            )
            entry = DailyEntryService(
                session, self.clock, workspace.id, housing_context=housing
            ).read(selected_date)
            kennel = KennelMapReadService(
                session, self.clock, workspace.id, housing_context=housing
            ).snapshot(selected_date)
            plan = plans._plan(selected_date)
            dogs = plans._all_dogs()
            dated = EffectiveDogState(selected_date, housing)
            workload = builder._workload([dog.id for dog in dogs], selected_date)
            planned = plans._planned_km(selected_date, None)
            actual = tuple(
                Actual(
                    id=item.id,
                    distance_km=item.distance_km,
                    participants=tuple(row.dog_id for row in item.participants),
                )
                for item in entry.sessions
            )
            dog_states = []
            for dog in sorted(dogs, key=lambda item: str(item.public_id)):
                metrics = workload.get(dog.id, (0, 0, 0, 0, None))
                where = dated.housing(dog)
                dog_states.append(
                    DogState(
                        id=dog.public_id,
                        name=dog.name,
                        born=dog.birth_date <= selected_date,
                        lifecycle=dated.lifecycle(dog),
                        dog_class=dated.dog_class(dog)[0],
                        availability=dated.availability(dog),
                        capabilities=cast(
                            tuple[Role, ...],
                            tuple(sorted(row.role for row in dog.role_capabilities)),
                        ),
                        housing_code=where.location.code if where else None,
                        housing_source="workspace_override"
                        if housing.override(dog.id, selected_date)
                        else "canonical"
                        if where
                        else "unhoused",
                        km_7d_before=metrics[0],
                        km_14d_before=metrics[1],
                        season_km_before=metrics[2],
                        starts_14d_before=metrics[3],
                        days_since_work_before=metrics[4],
                        actual_km_on_date=sum(
                            row.distance_km
                            for row in actual
                            if dog.public_id in row.participants
                        ),
                        starts_on_date=sum(
                            dog.public_id in row.participants for row in actual
                        ),
                    )
                )
            dog_lookup = {dog.id: dog for dog in dog_states}
            statuses = {
                item.id: item.actual_status for item in entry.planned_activities
            }
            activities: list[Activity] = []
            for item in sorted(
                plan.activities if plan else [], key=lambda row: row.sequence
            ):
                kind = PlannedActivityType(item.activity_type)
                eligibility = tuple(
                    plans._eligibility_read(
                        row.dog,
                        selected_date,
                        kind,
                        item.distance_km,
                        planned.get(row.dog_id, 0)
                        - (
                            item.distance_km or 0
                            if kind == PlannedActivityType.TRAINING
                            else 0
                        ),
                    )
                    for row in item.participants
                )
                candidates = {}
                for eligible in eligibility:
                    if not eligible.eligible:
                        continue
                    state = dog_lookup[eligible.id]
                    candidates[eligible.id] = Candidate(
                        str(state.id),
                        state.name,
                        frozenset(state.capabilities),
                        state.housing_code,
                        state.km_7d_before,
                        state.km_14d_before,
                        state.season_km_before,
                        state.starts_14d_before,
                        state.days_since_work_before,
                        planned.get(
                            next(
                                row.dog_id
                                for row in item.participants
                                if row.dog.public_id == state.id
                            ),
                            0,
                        ),
                    )
                saved = tuple(
                    SavedTeam(
                        sequence=team.sequence,
                        size=team.team_size,
                        slots=tuple(
                            SavedSlot(
                                dog_id=slot.dog.public_id,
                                pair_index=slot.pair_index,
                                side=slot.side,
                                role=slot.harness_role,
                                order=slot.position_order,
                            )
                            for slot in sorted(
                                team.slots, key=lambda slot: slot.position_order
                            )
                        ),
                    )
                    for team in sorted(item.teams, key=lambda team: team.sequence)
                )
                lineup_error = None
                if saved:
                    relationships = builder.relationships_for_dogs(
                        [row.dog_id for row in item.participants]
                    )
                    _, conflicts = builder._relationship_sets(relationships)
                    try:
                        writes = [
                            PlannedTeamWrite(
                                sequence=team.sequence,
                                team_size=team.size,
                                slots=[
                                    TeamSlotWrite(
                                        dog_id=slot.dog_id,
                                        pair_index=slot.pair_index,
                                        side=slot.side,
                                        harness_role=slot.role,
                                        position_order=slot.order,
                                    )
                                    for slot in team.slots
                                ],
                            )
                            for team in saved
                        ]
                        builder._validate_saved_lineup(writes, candidates, conflicts)
                        if kind != PlannedActivityType.TRAINING:
                            lineup_error = "training_required"
                    except TeamBuilderError as error:
                        lineup_error = error.code
                    except ValidationError:
                        lineup_error = "invalid_geometry"
                activities.append(
                    Activity(
                        id=item.public_id,
                        sequence=item.sequence,
                        kind=item.activity_type,
                        distance_km=item.distance_km,
                        participants=tuple(
                            row.dog.public_id for row in item.participants
                        ),
                        eligibility=tuple(
                            Eligibility(dog_id=row.id, reasons=tuple(row.reasons))
                            for row in eligibility
                        ),
                        teams=saved,
                        lineup_error=lineup_error,
                        actual_status=statuses.get(item.public_id, "not_recorded"),
                    )
                )
            locations = tuple(
                Location(
                    code=location.code,
                    nominal_capacity=location.capacity,
                    residents=tuple(row.id for row in location.residents),
                )
                for location in kennel.locations
            )
            checks, evidence = evaluate(
                selected_date,
                day=Entity(kind="day", id=selected_date.isoformat()),
                activities=tuple(activities),
                dogs=tuple(dog_states),
                actual=actual,
                locations=locations,
                plan_exists=plan is not None,
            )
            snapshot = Snapshot(
                id=uuid4(),
                captured_at=datetime.now(UTC),
                selected_date=selected_date,
                plan_exists=plan is not None,
                plan_revision=plan.revision if plan else None,
                activities=tuple(activities),
                dogs=tuple(dog_states),
                actual=actual,
                locations=locations,
                checks=checks,
                evidence=evidence,
            )
            if len(snapshot.model_dump_json().encode()) > 192_000:
                raise OperationError("snapshot_too_large")
            if workspace.expires_at <= datetime.now(UTC):
                raise OperationError("session_expired")
        # Both transaction and Session have ended before this detached value escapes.
        return RunContext(snapshot, binding)

    def check(
        self,
        context: RunContext,
        cookie: str | None,
        *,
        cancelled: bool | Callable[[], bool] = False,
        deadline: float | None = None,
    ) -> None:
        cancel_check = cancelled if callable(cancelled) else lambda: cancelled
        if cancel_check():
            raise OperationError("cancelled")
        with self._read_session(deadline, cancel_check) as session:
            workspace = resolve_workspace(session, cookie, self._secret)
            if workspace is None:
                raise OperationError("session_expired")
            if workspace.id != context._binding.workspace_id:
                raise OperationError("context_changed")
            workspace = lock_workspace(session, workspace.id)
            if workspace is None:
                raise OperationError("session_expired")
            current = _Binding(
                workspace.id,
                workspace.public_id,
                workspace.expires_at,
                workspace.housing_revision,
            )
            if current != context._binding:
                raise OperationError("context_changed")
        # housing_revision detects Reset and conservatively moves, not arbitrary edits.
