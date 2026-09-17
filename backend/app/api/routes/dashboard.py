from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.schemas.dashboard import DashboardRead
from app.services.analytics_service import AnalyticsRangeError
from app.services.dashboard_service import DashboardService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    session: DatabaseSession,
    selected_date: Annotated[date, Query(alias="date")],
) -> DashboardRead:
    try:
        return DashboardService(session, DemoClock.from_settings(get_settings())).read(
            selected_date
        )
    except AnalyticsRangeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
