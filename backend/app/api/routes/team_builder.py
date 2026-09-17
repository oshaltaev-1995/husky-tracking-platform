from collections.abc import Callable
from datetime import date
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.schemas.team_builder import (
    GeneratedTeamsRead,
    GenerateTeamsRequest,
    SaveTeamsRequest,
    TeamBuilderContextRead,
)
from app.services.daily_plan_service import DailyPlanError
from app.services.team_builder_service import TeamBuilderError, TeamBuilderService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
ResultT = TypeVar("ResultT")


def service(session: Session) -> TeamBuilderService:
    return TeamBuilderService(session, DemoClock.from_settings(get_settings()))


def run(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except (TeamBuilderError, DailyPlanError) as error:
        detail: dict[str, object] = {"code": error.code, "message": error.message}
        if isinstance(error, TeamBuilderError) and error.details:
            detail["details"] = error.details
        raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get(
    "/daily-plans/{plan_date}/activities/{activity_id}/team-builder",
    response_model=TeamBuilderContextRead,
)
def get_team_builder(
    plan_date: date, activity_id: UUID, session: DatabaseSession
) -> TeamBuilderContextRead:
    return run(lambda: service(session).context(plan_date, activity_id))


@router.post(
    "/daily-plans/{plan_date}/activities/{activity_id}/teams/generate",
    response_model=GeneratedTeamsRead,
)
def generate_teams(
    plan_date: date,
    activity_id: UUID,
    payload: GenerateTeamsRequest,
    session: DatabaseSession,
) -> GeneratedTeamsRead:
    return run(
        lambda: service(session).generate(
            plan_date,
            activity_id,
            team_count=payload.team_count,
            team_size=payload.team_size,
        )
    )


@router.put(
    "/daily-plans/{plan_date}/activities/{activity_id}/teams",
    response_model=TeamBuilderContextRead,
)
def save_teams(
    plan_date: date,
    activity_id: UUID,
    payload: SaveTeamsRequest,
    session: DatabaseSession,
) -> TeamBuilderContextRead:
    def operation() -> TeamBuilderContextRead:
        with session.begin():
            return service(session).save(plan_date, activity_id, payload)

    return run(operation)
