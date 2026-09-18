from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Response

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import DemoWorkspace
from app.services.demo_workspace_service import (
    COOKIE_NAME,
    create_workspace,
    resolve_workspace,
)


@dataclass(frozen=True)
class DemoWorkspaceContext:
    workspace: DemoWorkspace
    created: bool
    replaced_expired: bool


def get_demo_workspace(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> DemoWorkspaceContext:
    with SessionLocal.begin() as session:
        workspace = resolve_workspace(session, token)
        if workspace is not None:
            session.expunge(workspace)
            response.headers["X-Demo-Session-State"] = "active"
            response.headers["X-Demo-Session-Expires-At"] = (
                workspace.expires_at.isoformat()
            )
            return DemoWorkspaceContext(workspace, False, False)
        issued = create_workspace(session, settings.demo_workspace_ttl_hours)
        session.expunge(issued.workspace)
    response.set_cookie(
        key=COOKIE_NAME,
        value=issued.token,
        max_age=settings.demo_workspace_ttl_hours * 3600,
        httponly=True,
        secure=settings.demo_cookie_secure,
        samesite="lax",
        path=settings.api_v1_prefix,
    )
    response.headers["X-Demo-Session-State"] = (
        "replaced-expired" if token is not None else "created"
    )
    response.headers["X-Demo-Session-Expires-At"] = (
        issued.workspace.expires_at.isoformat()
    )
    return DemoWorkspaceContext(issued.workspace, True, token is not None)
