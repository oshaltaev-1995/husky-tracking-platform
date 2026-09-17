from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.demo_clock import DemoClock

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
