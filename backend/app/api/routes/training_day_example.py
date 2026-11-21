from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.demo_workspace import (
    DemoWorkspaceContext,
    get_existing_demo_workspace,
)
from app.api.routes.daily_plans import run
from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.schemas.daily_plans import DailyPlanRead
from app.schemas.training_day_example import TrainingDayApply, TrainingDayProposal
from app.services.training_day_example_service import TrainingDayExampleService

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]
Workspace = Annotated[DemoWorkspaceContext, Depends(get_existing_demo_workspace)]


def service(
    session: Session, workspace: DemoWorkspaceContext
) -> TrainingDayExampleService:
    return TrainingDayExampleService(
        session, DemoClock.from_settings(get_settings()), workspace.workspace.id
    )


@router.get("/training-day-example", response_model=TrainingDayProposal)
def preview_training_day(
    session: Database, workspace: Workspace
) -> TrainingDayProposal:
    return run(lambda: service(session, workspace).preview())


@router.post("/training-day-example/apply", response_model=DailyPlanRead)
def apply_training_day(
    payload: TrainingDayApply, session: Database, workspace: Workspace
) -> DailyPlanRead:
    def operation() -> DailyPlanRead:
        with session.begin():
            return service(session, workspace).apply(payload)

    return run(operation)
