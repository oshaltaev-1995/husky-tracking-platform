from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.demo_workspace import DemoWorkspaceContext, get_demo_workspace
from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.models.enums import (
    ArchiveReason,
    AvailabilityState,
    DogClass,
    DogSex,
    WorkingRole,
)
from app.schemas.dogs import (
    ArchiveRegistryRead,
    ArchiveSort,
    DogHistoryRead,
    DogPedigreeRead,
    DogProfileRead,
    DogSort,
    DogsRegistryRead,
    DogWorkRead,
)
from app.services.dog_read_service import DogReadService

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
Workspace = Annotated[DemoWorkspaceContext, Depends(get_demo_workspace)]


def service(session: Session, workspace: DemoWorkspaceContext) -> DogReadService:
    return DogReadService(
        session, DemoClock.from_settings(get_settings()), workspace.workspace.id
    )


@router.get("/dogs", response_model=DogsRegistryRead)
def dogs_registry(
    session: DatabaseSession,
    workspace: Workspace,
    search: Annotated[str | None, Query(max_length=80)] = None,
    dog_class: DogClass | None = None,
    sex: DogSex | None = None,
    availability: AvailabilityState | None = None,
    neutered: bool | None = None,
    housing: Annotated[str | None, Query(max_length=30)] = None,
    capability: WorkingRole | None = None,
    sort: DogSort = DogSort.NAME,
) -> DogsRegistryRead:
    return service(session, workspace).list_active(
        search=search,
        dog_class=dog_class.value if dog_class else None,
        sex=sex.value if sex else None,
        availability=availability.value if availability else None,
        neutered=neutered,
        housing=housing,
        capability=capability.value if capability else None,
        sort=sort,
    )


@router.get("/archive", response_model=ArchiveRegistryRead)
def archive_registry(
    session: DatabaseSession,
    workspace: Workspace,
    search: Annotated[str | None, Query(max_length=80)] = None,
    reason: ArchiveReason | None = None,
    sort: ArchiveSort = ArchiveSort.NAME,
) -> ArchiveRegistryRead:
    return service(session, workspace).list_archived(
        search=search,
        reason=reason.value if reason else None,
        sort=sort,
    )


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="dog not found")


@router.get("/dogs/{dog_id}", response_model=DogProfileRead)
def dog_profile(
    dog_id: UUID, session: DatabaseSession, workspace: Workspace
) -> DogProfileRead:
    result = service(session, workspace).profile(dog_id)
    if not result:
        raise not_found()
    return result


@router.get("/dogs/{dog_id}/pedigree", response_model=DogPedigreeRead)
def dog_pedigree(
    dog_id: UUID, session: DatabaseSession, workspace: Workspace
) -> DogPedigreeRead:
    result = service(session, workspace).pedigree(dog_id)
    if not result:
        raise not_found()
    return result


@router.get("/dogs/{dog_id}/work", response_model=DogWorkRead)
def dog_work(
    dog_id: UUID, session: DatabaseSession, workspace: Workspace
) -> DogWorkRead:
    result = service(session, workspace).work(dog_id)
    if not result:
        raise not_found()
    return result


@router.get("/dogs/{dog_id}/history", response_model=DogHistoryRead)
def dog_history(
    dog_id: UUID, session: DatabaseSession, workspace: Workspace
) -> DogHistoryRead:
    result = service(session, workspace).history(dog_id)
    if not result:
        raise not_found()
    return result
