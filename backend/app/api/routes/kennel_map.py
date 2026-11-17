from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.demo_workspace import (
    DemoWorkspaceContext,
    get_existing_demo_workspace,
    get_optional_demo_workspace,
)
from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.schemas.kennel_map import HousingMovesRequest, KennelMapSnapshotRead
from app.services.housing_move_service import HousingMoveError, HousingMoveService
from app.services.kennel_map_read_service import KennelMapReadService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
OptionalWorkspace = Annotated[
    DemoWorkspaceContext | None, Depends(get_optional_demo_workspace)
]
ExistingWorkspace = Annotated[
    DemoWorkspaceContext, Depends(get_existing_demo_workspace)
]


@router.get("/kennel-map", response_model=KennelMapSnapshotRead)
def kennel_map_snapshot(
    session: DatabaseSession,
    workspace: OptionalWorkspace,
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
    with session.begin():
        return KennelMapReadService(
            session, clock, workspace.workspace.id if workspace else None
        ).snapshot(on_date)


@router.post("/kennel-map/moves", response_model=KennelMapSnapshotRead)
def move_kennel_dogs(
    payload: HousingMovesRequest,
    session: DatabaseSession,
    workspace: ExistingWorkspace,
) -> KennelMapSnapshotRead:
    try:
        with session.begin():
            return HousingMoveService(
                session,
                DemoClock.from_settings(get_settings()),
                workspace.workspace.id,
            ).apply(payload)
    except HousingMoveError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error
