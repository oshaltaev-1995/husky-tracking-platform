from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.models import DemoWorkspace, DemoWorkspaceHousingOverride, KennelLocation


@dataclass(frozen=True, slots=True)
class HousingLocation:
    """A point-in-time location, not a fabricated canonical history period."""

    location_id: int
    location: KennelLocation


@dataclass(frozen=True, slots=True)
class HousingContext:
    """One explicitly scoped, locked housing projection for the current request."""

    reference_date: date
    workspace_id: int | None = None
    revision: int | None = None
    precondition: str | None = None
    overrides: dict[int, HousingLocation] = field(default_factory=dict)

    def override(self, dog_id: int, on_date: date) -> HousingLocation | None:
        if on_date != self.reference_date:
            return None
        return self.overrides.get(dog_id)


def lock_workspace(session: Session, workspace_id: int) -> DemoWorkspace | None:
    """Serialize moves, reset, and projection reads against cleanup and each other."""
    workspace = session.scalar(
        select(DemoWorkspace)
        .where(DemoWorkspace.id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # Check after the lock is acquired: the request may have waited beyond expiry.
    if (
        workspace is None
        or workspace.expires_at <= datetime.now(UTC)
        or workspace.schema_version != 1
    ):
        return None
    return workspace


def housing_precondition(workspace: DemoWorkspace, reference_date: date) -> str:
    message = (
        f"housing-v1:{workspace.public_id}:{reference_date.isoformat()}:"
        f"{workspace.housing_revision}"
    )
    signature = hmac.new(
        get_settings().demo_session_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"h1.{signature}"


def load_housing_context(
    session: Session, clock: DemoClock, workspace_id: int | None
) -> HousingContext:
    if workspace_id is None:
        return HousingContext(clock.reference_date)
    workspace = lock_workspace(session, workspace_id)
    if workspace is None:
        return HousingContext(clock.reference_date)
    overrides = session.scalars(
        select(DemoWorkspaceHousingOverride)
        .where(
            DemoWorkspaceHousingOverride.workspace_id == workspace.id,
            DemoWorkspaceHousingOverride.effective_date == clock.reference_date,
        )
        .options(joinedload(DemoWorkspaceHousingOverride.location))
        .execution_options(populate_existing=True)
    )
    return HousingContext(
        reference_date=clock.reference_date,
        workspace_id=workspace.id,
        revision=workspace.housing_revision,
        precondition=housing_precondition(workspace, clock.reference_date),
        overrides={
            item.dog_id: HousingLocation(item.location_id, item.location)
            for item in overrides
        },
    )
