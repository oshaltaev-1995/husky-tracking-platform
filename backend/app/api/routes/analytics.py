from collections.abc import Callable
from datetime import date
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.models.enums import DogClass
from app.schemas.analytics import (
    AnalyticsDogSort,
    AnalyticsDogsRead,
    AnalyticsOverviewRead,
    PopulationAnalyticsRead,
)
from app.services.analytics_service import AnalyticsRangeError, AnalyticsService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
ResultT = TypeVar("ResultT")


def service(session: Session) -> AnalyticsService:
    return AnalyticsService(session, DemoClock.from_settings(get_settings()))


def run(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except AnalyticsRangeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/analytics/overview", response_model=AnalyticsOverviewRead)
def analytics_overview(
    session: DatabaseSession,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> AnalyticsOverviewRead:
    return run(lambda: service(session).overview(date_from, date_to))


@router.get("/analytics/population", response_model=PopulationAnalyticsRead)
def population_analytics(
    session: DatabaseSession,
    snapshot_date: Annotated[date, Query(alias="date")],
) -> PopulationAnalyticsRead:
    return run(lambda: service(session).population(snapshot_date))


@router.get("/analytics/dogs", response_model=AnalyticsDogsRead)
def analytics_dogs(
    session: DatabaseSession,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    search: Annotated[str | None, Query(max_length=80)] = None,
    dog_class: DogClass | None = None,
    sort: AnalyticsDogSort = AnalyticsDogSort.HIGHEST_KM,
) -> AnalyticsDogsRead:
    return run(
        lambda: service(session).dogs(
            date_from,
            date_to,
            search=search,
            dog_class=dog_class.value if dog_class else None,
            sort=sort,
        )
    )
