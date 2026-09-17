from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.schemas.kennel_map import KennelMapSnapshotRead
from app.services.kennel_map_read_service import KennelMapReadService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/kennel-map", response_model=KennelMapSnapshotRead)
def kennel_map_snapshot(
    session: DatabaseSession,
    snapshot_date: Annotated[date | None, Query(alias="date")] = None,
) -> KennelMapSnapshotRead:
    clock = DemoClock.from_settings(get_settings())
    on_date = snapshot_date or clock.reference_date
    if not clock.season_start <= on_date <= clock.season_end:
        raise HTTPException(
            status_code=422,
            detail=(
                "map date must be within the demo season "
                f"{clock.season_start.isoformat()} through "
                f"{clock.season_end.isoformat()}"
            ),
        )
    return KennelMapReadService(session, clock).snapshot(on_date)
