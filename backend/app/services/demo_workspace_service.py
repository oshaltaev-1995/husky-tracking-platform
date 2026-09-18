from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, exists, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    DailyPlan,
    DemoWorkspace,
    DemoWorkspaceDay,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)

COOKIE_NAME = "ht_demo_session"
WORKSPACE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WorkspaceToken:
    workspace: DemoWorkspace
    token: str


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_workspace(session: Session, ttl_hours: int) -> WorkspaceToken:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    workspace = DemoWorkspace(
        token_hash=token_digest(token),
        schema_version=WORKSPACE_SCHEMA_VERSION,
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    session.add(workspace)
    session.flush()
    return WorkspaceToken(workspace=workspace, token=token)


def resolve_workspace(session: Session, token: str | None) -> DemoWorkspace | None:
    if not token or not 20 <= len(token) <= 200:
        return None
    now = datetime.now(UTC)
    return session.scalar(
        select(DemoWorkspace).where(
            DemoWorkspace.token_hash == token_digest(token),
            DemoWorkspace.expires_at > now,
            DemoWorkspace.schema_version == WORKSPACE_SCHEMA_VERSION,
        )
    )


def scoped_date_filter(
    model: Any, workspace_id: int | None, field: Any
) -> ColumnElement[bool]:
    if workspace_id is None:
        return cast(ColumnElement[bool], model.demo_workspace_id.is_(None))
    materialized = exists(
        select(DemoWorkspaceDay.id).where(
            DemoWorkspaceDay.workspace_id == workspace_id,
            DemoWorkspaceDay.work_date == field,
        )
    )
    return or_(
        model.demo_workspace_id == workspace_id,
        and_(model.demo_workspace_id.is_(None), ~materialized),
    )


class DemoWorkspaceService:
    def __init__(self, session: Session, workspace_id: int) -> None:
        self.session = session
        self.workspace_id = workspace_id

    def materialize_date(self, work_date: date) -> None:
        workspace = self.session.scalar(
            select(DemoWorkspace)
            .where(DemoWorkspace.id == self.workspace_id)
            .with_for_update()
        )
        if workspace is None or workspace.expires_at <= datetime.now(UTC):
            raise RuntimeError("demo workspace expired")
        if self.session.scalar(
            select(DemoWorkspaceDay.id).where(
                DemoWorkspaceDay.workspace_id == self.workspace_id,
                DemoWorkspaceDay.work_date == work_date,
            )
        ):
            return

        plan = self.session.scalar(
            select(DailyPlan)
            .where(
                DailyPlan.demo_workspace_id.is_(None), DailyPlan.plan_date == work_date
            )
            .options(
                selectinload(DailyPlan.activities).selectinload(
                    PlannedActivity.participants
                ),
                selectinload(DailyPlan.activities)
                .selectinload(PlannedActivity.teams)
                .selectinload(PlannedTeam.slots),
            )
        )
        activity_map: dict[int, PlannedActivity] = {}
        if plan is not None:
            plan_copy = DailyPlan(
                public_id=plan.public_id,
                demo_workspace_id=self.workspace_id,
                plan_date=plan.plan_date,
                notes=plan.notes,
                revision=plan.revision,
            )
            self.session.add(plan_copy)
            self.session.flush()
            for activity in sorted(plan.activities, key=lambda item: item.sequence):
                activity_copy = PlannedActivity(
                    public_id=activity.public_id,
                    daily_plan_id=plan_copy.id,
                    activity_type=activity.activity_type,
                    sequence=activity.sequence,
                    start_time=activity.start_time,
                    title=activity.title,
                    distance_km=activity.distance_km,
                    notes=activity.notes,
                    actual_not_run=activity.actual_not_run,
                )
                activity_copy.participants = [
                    PlannedActivityParticipant(dog_id=item.dog_id)
                    for item in activity.participants
                ]
                self.session.add(activity_copy)
                self.session.flush()
                activity_map[activity.id] = activity_copy
                for team in sorted(activity.teams, key=lambda item: item.sequence):
                    team_copy = PlannedTeam(
                        planned_activity_id=activity_copy.id,
                        sequence=team.sequence,
                        team_size=team.team_size,
                        display_label=team.display_label,
                    )
                    self.session.add(team_copy)
                    self.session.flush()
                    team_copy.slots = [
                        PlannedTeamSlot(
                            planned_activity_id=activity_copy.id,
                            dog_id=slot.dog_id,
                            pair_index=slot.pair_index,
                            side=slot.side,
                            harness_role=slot.harness_role,
                            position_order=slot.position_order,
                        )
                        for slot in team.slots
                    ]

        sessions = list(
            self.session.scalars(
                select(WorkSession)
                .where(
                    WorkSession.demo_workspace_id.is_(None),
                    WorkSession.work_date == work_date,
                )
                .options(selectinload(WorkSession.participations))
            ).unique()
        )
        for item in sessions:
            clone = WorkSession(
                public_id=item.public_id,
                source_reference=item.source_reference,
                demo_workspace_id=self.workspace_id,
                planned_activity_id=(
                    activity_map[item.planned_activity_id].id
                    if item.planned_activity_id in activity_map
                    else None
                ),
                work_date=item.work_date,
                start_time=item.start_time,
                distance_km=item.distance_km,
                activity_type=item.activity_type,
                label=item.label,
                note=item.note,
                revision=item.revision,
            )
            clone.participations = [
                WorkParticipation(
                    dog_id=row.dog_id,
                    assigned_role=row.assigned_role,
                    actual_team_sequence=row.actual_team_sequence,
                    pair_index=row.pair_index,
                    side=row.side,
                    position_order=row.position_order,
                )
                for row in item.participations
            ]
            self.session.add(clone)

        self.session.add(
            DemoWorkspaceDay(workspace_id=self.workspace_id, work_date=work_date)
        )
        self.session.flush()

    def reset(self) -> None:
        self.session.execute(
            delete(DailyPlan).where(DailyPlan.demo_workspace_id == self.workspace_id)
        )
        self.session.execute(
            delete(WorkSession).where(
                WorkSession.demo_workspace_id == self.workspace_id
            )
        )
        self.session.execute(
            delete(DemoWorkspaceDay).where(
                DemoWorkspaceDay.workspace_id == self.workspace_id
            )
        )


def cleanup_expired_workspaces(session: Session, now: datetime | None = None) -> int:
    result = session.execute(
        delete(DemoWorkspace).where(
            DemoWorkspace.expires_at <= (now or datetime.now(UTC))
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)
