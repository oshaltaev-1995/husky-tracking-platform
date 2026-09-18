from datetime import date

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    demo_season: str
    demo_season_start: date
    demo_season_end: date
    demo_reference_date: date


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    clock = DemoClock.from_settings(settings)
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        demo_season=clock.season_label,
        demo_season_start=clock.season_start,
        demo_season_end=clock.season_end,
        demo_reference_date=clock.reference_date,
    )


class ReadinessResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/ready", response_model=ReadinessResponse)
def ready(response: Response) -> ReadinessResponse:
    settings = get_settings()
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unavailable",
            service=settings.app_name,
            version=settings.app_version,
        )
    return ReadinessResponse(
        status="ready",
        service=settings.app_name,
        version=settings.app_version,
    )
