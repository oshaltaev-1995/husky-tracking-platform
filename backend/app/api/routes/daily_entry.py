from collections.abc import Callable
from datetime import date
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.demo_workspace import DemoWorkspaceContext, get_demo_workspace
from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.schemas.daily_entry import (
    ActualEligibilityRead,
    ActualSessionCreate,
    ActualSessionUpdate,
    DailyEntryRead,
)
from app.services.daily_entry_service import DailyEntryError, DailyEntryService
from app.services.daily_plan_service import DailyPlanError

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
Workspace = Annotated[DemoWorkspaceContext, Depends(get_demo_workspace)]
ResultT = TypeVar("ResultT")


def service(session: Session, workspace: DemoWorkspaceContext) -> DailyEntryService:
    return DailyEntryService(
        session, DemoClock.from_settings(get_settings()), workspace.workspace.id
    )


def run(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except (DailyEntryError, DailyPlanError) as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.get("/daily-entry/{work_date}", response_model=DailyEntryRead)
def get_daily_entry(
    work_date: date, session: DatabaseSession, workspace: Workspace
) -> DailyEntryRead:
    return run(lambda: service(session, workspace).read(work_date))


@router.get(
    "/daily-entry/{work_date}/eligible-dogs",
    response_model=ActualEligibilityRead,
)
def eligible_dogs(
    work_date: date,
    distance_km: Annotated[int, Query()],
    session: DatabaseSession,
    workspace: Workspace,
    exclude_session_id: Annotated[UUID | None, Query()] = None,
) -> ActualEligibilityRead:
    return run(
        lambda: service(session, workspace).eligibility(
            work_date,
            distance_km,
            exclude_session_id=exclude_session_id,
        )
    )


@router.post("/daily-entry/{work_date}/sessions", response_model=DailyEntryRead)
def create_actual_session(
    work_date: date,
    payload: ActualSessionCreate,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyEntryRead:
    def operation() -> DailyEntryRead:
        with session.begin():
            return service(session, workspace).create_manual(work_date, payload)

    return run(operation)


@router.patch(
    "/daily-entry/{work_date}/sessions/{session_id}",
    response_model=DailyEntryRead,
)
def update_actual_session(
    work_date: date,
    session_id: UUID,
    payload: ActualSessionUpdate,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyEntryRead:
    def operation() -> DailyEntryRead:
        with session.begin():
            return service(session, workspace).update(work_date, session_id, payload)

    return run(operation)


@router.delete(
    "/daily-entry/{work_date}/sessions/{session_id}",
    response_model=DailyEntryRead,
)
def delete_actual_session(
    work_date: date,
    session_id: UUID,
    expected_revision: Annotated[int, Query(ge=1)],
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyEntryRead:
    def operation() -> DailyEntryRead:
        with session.begin():
            return service(session, workspace).delete(
                work_date, session_id, expected_revision
            )

    return run(operation)


@router.post(
    "/daily-entry/{work_date}/planned-activities/{activity_id}/confirm",
    response_model=DailyEntryRead,
)
def confirm_planned_training(
    work_date: date,
    activity_id: UUID,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyEntryRead:
    def operation() -> DailyEntryRead:
        with session.begin():
            return service(session, workspace).confirm_plan(work_date, activity_id)

    return run(operation)


@router.post(
    "/daily-entry/{work_date}/planned-activities/{activity_id}/not-run",
    response_model=DailyEntryRead,
)
def mark_planned_training_not_run(
    work_date: date,
    activity_id: UUID,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyEntryRead:
    def operation() -> DailyEntryRead:
        with session.begin():
            return service(session, workspace).mark_not_run(work_date, activity_id)

    return run(operation)


@router.delete(
    "/daily-entry/{work_date}/planned-activities/{activity_id}/not-run",
    response_model=DailyEntryRead,
)
def clear_planned_training_not_run(
    work_date: date,
    activity_id: UUID,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyEntryRead:
    def operation() -> DailyEntryRead:
        with session.begin():
            return service(session, workspace).clear_not_run(work_date, activity_id)

    return run(operation)
