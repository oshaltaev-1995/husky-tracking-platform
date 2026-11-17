from __future__ import annotations

import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.demo_clock import DemoClock
from app.models import DemoWorkspace, DemoWorkspaceHousingOverride, Dog, KennelLocation
from app.schemas.kennel_map import HousingMovesRequest, KennelMapSnapshotRead
from app.services.effective_state import EffectiveDogState
from app.services.housing_context import load_housing_context
from app.services.kennel_map_read_service import KennelMapReadService


class HousingMoveError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class HousingMoveService:
    """Atomic reference-date overrides; never materialize a plan or actual ledger."""

    def __init__(self, session: Session, clock: DemoClock, workspace_id: int) -> None:
        self.session = session
        self.clock = clock
        self.workspace_id = workspace_id

    def apply(self, payload: HousingMovesRequest) -> KennelMapSnapshotRead:
        context = load_housing_context(self.session, self.clock, self.workspace_id)
        if context.workspace_id is None:
            raise HousingMoveError(
                "housing_session_required", "Open a current demo session first.", 401
            )
        if payload.effective_date != self.clock.reference_date:
            raise HousingMoveError(
                "housing_date_read_only", "Housing changes use the demo reference date."
            )
        if context.precondition is None or not hmac.compare_digest(
            payload.precondition.encode(), context.precondition.encode()
        ):
            raise HousingMoveError(
                "housing_changed",
                "Housing changed. Reload before confirming moves.",
                409,
            )
        dog_ids = [move.dog_id for move in payload.moves]
        if len(set(dog_ids)) != len(dog_ids):
            raise HousingMoveError(
                "housing_duplicate_dog",
                "Each dog may appear only once in a move batch.",
            )
        dogs = {
            dog.public_id: dog
            for dog in self.session.scalars(
                select(Dog)
                .where(Dog.public_id.in_(dog_ids))
                .options(
                    selectinload(Dog.lifecycle_periods),
                    selectinload(Dog.housing_assignments),
                )
            )
        }
        destinations = {move.destination_code for move in payload.moves}
        locations = {
            location.code: location
            for location in self.session.scalars(
                select(KennelLocation).where(
                    KennelLocation.code.in_(destinations),
                    KennelLocation.is_active.is_(True),
                )
            )
        }
        baseline = EffectiveDogState(self.clock.reference_date)
        state = EffectiveDogState(self.clock.reference_date, context)
        # Validate the entire request before touching any override or revision.
        for move in payload.moves:
            dog = dogs.get(move.dog_id)
            if dog is None:
                raise HousingMoveError(
                    "housing_unknown_dog", "A selected dog was not found."
                )
            if (
                dog.birth_date > self.clock.reference_date
                or baseline.lifecycle(dog) != "active"
            ):
                raise HousingMoveError(
                    "housing_dog_inactive", "Only born, active dogs can be moved."
                )
            if move.destination_code not in locations:
                raise HousingMoveError(
                    "housing_invalid_destination", "Choose an active kennel location."
                )

        overrides = {
            item.dog_id: item
            for item in self.session.scalars(
                select(DemoWorkspaceHousingOverride).where(
                    DemoWorkspaceHousingOverride.workspace_id == self.workspace_id,
                    DemoWorkspaceHousingOverride.effective_date
                    == self.clock.reference_date,
                )
            )
        }
        changed = False
        for move in payload.moves:
            dog = dogs[move.dog_id]
            destination = locations[move.destination_code]
            current = state.housing(dog)
            if current is not None and current.location_id == destination.id:
                continue
            changed = True
            original = baseline.housing(dog)
            existing = overrides.get(dog.id)
            if original is not None and original.location_id == destination.id:
                if existing is not None:
                    self.session.delete(existing)
            elif existing is not None:
                existing.location_id = destination.id
            else:
                self.session.add(
                    DemoWorkspaceHousingOverride(
                        workspace_id=self.workspace_id,
                        dog_id=dog.id,
                        effective_date=self.clock.reference_date,
                        location_id=destination.id,
                    )
                )
        if changed:
            workspace = self.session.get(DemoWorkspace, self.workspace_id)
            assert workspace is not None  # Held by the context's row lock.
            workspace.housing_revision += 1
            self.session.flush()
            context = load_housing_context(self.session, self.clock, self.workspace_id)
        return KennelMapReadService(
            self.session, self.clock, self.workspace_id, housing_context=context
        ).snapshot(self.clock.reference_date)
