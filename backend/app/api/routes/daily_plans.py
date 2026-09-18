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
from app.models.enums import PlannedActivityType
from app.schemas.daily_plans import (
    ActivityMove,
    ActivityWrite,
    DailyPlanRead,
    EligibilityRead,
    PlanNoteUpdate,
)
from app.services.daily_plan_service import DailyPlanError, DailyPlanService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
Workspace = Annotated[DemoWorkspaceContext, Depends(get_demo_workspace)]
ResultT = TypeVar("ResultT")


def service(session: Session, workspace: DemoWorkspaceContext) -> DailyPlanService:
    return DailyPlanService(
        session, DemoClock.from_settings(get_settings()), workspace.workspace.id
    )


def run(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except DailyPlanError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.get("/daily-plans/{plan_date}", response_model=DailyPlanRead)
def get_daily_plan(
    plan_date: date, session: DatabaseSession, workspace: Workspace
) -> DailyPlanRead:
    return run(lambda: service(session, workspace).read(plan_date))


@router.put("/daily-plans/{plan_date}", response_model=DailyPlanRead)
def update_daily_plan(
    plan_date: date,
    payload: PlanNoteUpdate,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyPlanRead:
    def operation() -> DailyPlanRead:
        with session.begin():
            return service(session, workspace).update_notes(
                plan_date, payload.notes, payload.expected_revision
            )

    return run(operation)


@router.post("/daily-plans/{plan_date}/activities", response_model=DailyPlanRead)
def create_activity(
    plan_date: date,
    payload: ActivityWrite,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyPlanRead:
    def operation() -> DailyPlanRead:
        with session.begin():
            return service(session, workspace).create_activity(plan_date, payload)

    return run(operation)


@router.patch(
    "/daily-plans/{plan_date}/activities/{activity_id}",
    response_model=DailyPlanRead,
)
def update_activity(
    plan_date: date,
    activity_id: UUID,
    payload: ActivityWrite,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyPlanRead:
    def operation() -> DailyPlanRead:
        with session.begin():
            return service(session, workspace).update_activity(
                plan_date, activity_id, payload
            )

    return run(operation)


@router.post(
    "/daily-plans/{plan_date}/activities/{activity_id}/move",
    response_model=DailyPlanRead,
)
def move_activity(
    plan_date: date,
    activity_id: UUID,
    payload: ActivityMove,
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyPlanRead:
    def operation() -> DailyPlanRead:
        with session.begin():
            return service(session, workspace).move_activity(
                plan_date,
                activity_id,
                payload.direction.value,
                payload.expected_revision,
            )

    return run(operation)


@router.delete(
    "/daily-plans/{plan_date}/activities/{activity_id}",
    response_model=DailyPlanRead,
)
def delete_activity(
    plan_date: date,
    activity_id: UUID,
    expected_revision: Annotated[int, Query(ge=1)],
    session: DatabaseSession,
    workspace: Workspace,
) -> DailyPlanRead:
    def operation() -> DailyPlanRead:
        with session.begin():
            return service(session, workspace).delete_activity(
                plan_date, activity_id, expected_revision
            )

    return run(operation)


@router.get("/daily-plans/{plan_date}/eligible-dogs", response_model=EligibilityRead)
def eligible_dogs(
    plan_date: date,
    activity_type: PlannedActivityType,
    session: DatabaseSession,
    workspace: Workspace,
    distance_km: Annotated[int | None, Query()] = None,
    exclude_activity_id: Annotated[UUID | None, Query()] = None,
) -> EligibilityRead:
    return run(
        lambda: service(session, workspace).eligibility(
            plan_date,
            activity_type,
            distance_km,
            exclude_activity_id=exclude_activity_id,
        )
    )
