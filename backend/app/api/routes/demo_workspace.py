from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.demo_workspace import DemoWorkspaceContext, get_demo_workspace
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.operations.provider_models import AgentFailure, get_provider_settings
from app.schemas.demo_workspace import DemoResetRead, DemoSessionRead, PrivacyRead
from app.services.demo_workspace_service import (
    DemoWorkspaceExpiredError,
    DemoWorkspaceService,
)

router = APIRouter()
Workspace = Annotated[DemoWorkspaceContext, Depends(get_demo_workspace)]
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/demo/session", response_model=DemoSessionRead)
def demo_session(
    workspace: Workspace, settings: Annotated[Settings, Depends(get_settings)]
) -> DemoSessionRead:
    return DemoSessionRead(
        expires_at=workspace.workspace.expires_at,
        ttl_hours=settings.demo_workspace_ttl_hours,
        ttl_seconds=settings.demo_workspace_ttl_hours * 3600,
        created=workspace.created,
        replaced_expired=workspace.replaced_expired,
    )


@router.post("/demo/reset", response_model=DemoResetRead)
def reset_demo_workspace(
    workspace: Workspace, session: DatabaseSession
) -> DemoResetRead:
    try:
        with session.begin():
            DemoWorkspaceService(session, workspace.workspace.id).reset()
    except DemoWorkspaceExpiredError as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "demo_session_expired", "message": str(error)},
        ) from error
    return DemoResetRead(status="reset", expires_at=workspace.workspace.expires_at)


@router.get("/public/privacy", response_model=PrivacyRead)
def privacy(settings: Annotated[Settings, Depends(get_settings)]) -> PrivacyRead:
    try:
        operations_enabled = get_provider_settings().enabled
    except AgentFailure:
        # Invalid optional agent settings cannot break the public privacy notice.
        operations_enabled = False
    return PrivacyRead(
        controller_name=settings.privacy_controller_name,
        contact_email=settings.privacy_contact_email,
        controller_country=settings.privacy_controller_country,
        hosting_region=settings.privacy_hosting_region,
        effective_date=settings.privacy_effective_date.isoformat(),
        mail_provider_name=settings.privacy_mail_provider_name,
        mail_provider_region=settings.privacy_mail_provider_region,
        demo_workspace_ttl_hours=settings.demo_workspace_ttl_hours,
        operations_review_enabled=operations_enabled,
    )
