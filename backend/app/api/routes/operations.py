"""Narrow same-origin review endpoint. Private ingress is the rate-limit authority."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from contextlib import suppress
from time import monotonic
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response

from app.core.config import Settings, get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.operations.api_schemas import (
    OperationsCapabilities,
    OperationsReviewRead,
    ReviewRequest,
)
from app.operations.http_transport import HTTPSProviderTransport
from app.operations.provider_models import (
    AgentFailure,
    ProviderSettings,
    get_provider_settings,
)
from app.operations.review import OperationsReviewService, TransportFactory
from app.operations.snapshot import SnapshotReader
from app.services.demo_workspace_service import COOKIE_NAME

logger = logging.getLogger("uvicorn.error")
PER_WORKER_REVIEW_LIMIT = 1
# Concurrency only, not an account/per-visitor rate counter. Nginx owns the public
# per-IP admission across backend workers; backend port remains private.
_review_slots = threading.BoundedSemaphore(PER_WORKER_REVIEW_LIMIT)

ERROR_MESSAGES = {
    "agent_disabled": "Operations review is not enabled in this environment.",
    "app_rate_limited": "Please wait before starting another operations review.",
    "review_busy": "An operations review is already running. Please try again shortly.",
    "session_required": "Open a current demo session before reviewing operations.",
    "session_expired": "Your demo session expired. Reopen the demo before reviewing.",
    "context_changed": "The demo was reset or changed. Review the current day again.",
    "cancelled": "The review was cancelled; an already sent provider "
    "request may finish.",
    "timeout": "The review reached its time limit. No result was accepted.",
    "date_out_of_range": "Choose a date within the demo season.",
    "snapshot_too_large": "This day has more detail than a review can read.",
    "run_budget_exhausted": "The review reached its request or data budget.",
    "ai_quota_exhausted": "AI review is currently rate or quota limited. "
    "Try again later.",
    "ai_temporarily_unavailable": "AI review is temporarily unavailable. "
    "Please try again later.",
    "provider_configuration": "Operations review configuration is incomplete "
    "or unavailable.",
    "provider_authentication": "The AI provider credentials need operator attention.",
    "provider_access_denied": "The AI provider did not allow this request.",
    "provider_payment_required": "A free AI route was not available; "
    "no paid request was made.",
    "invalid_provider_response": "The AI response could not be validated. "
    "No result was accepted.",
    "invalid_evidence": "The AI response used unsupported evidence. "
    "No result was accepted.",
    "forbidden_tool": "The AI requested a tool outside this read-only review.",
    "policy_refusal": "The AI provider declined this review.",
    "origin_not_allowed": "Start this review from the current application.",
}


def review_error(
    code: str, status: int, retry_after: int | None = None
) -> HTTPException:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": ERROR_MESSAGES.get(
                code, "The operations review could not complete."
            ),
            "retry_after_seconds": retry_after,
        },
        headers=headers,
    )


class SafeReviewRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                # Never echo a rejected prompt, settings field or arbitrary body.
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": {
                            "code": "invalid_review_request",
                            "message": "Select one demo date; "
                            "other review fields are not accepted.",
                            "retry_after_seconds": None,
                        }
                    },
                )

        return handler


router = APIRouter(route_class=SafeReviewRoute)


def operations_settings() -> ProviderSettings:
    try:
        return get_provider_settings()
    except AgentFailure:
        raise review_error("provider_configuration", 503) from None


def operations_transport_factory() -> TransportFactory:
    return lambda cancelled: HTTPSProviderTransport(cancelled=cancelled)


def operations_service(
    provider: Annotated[ProviderSettings, Depends(operations_settings)],
    settings: Annotated[Settings, Depends(get_settings)],
    factory: Annotated[TransportFactory, Depends(operations_transport_factory)],
) -> OperationsReviewService:
    return OperationsReviewService(
        SnapshotReader(
            SessionLocal,
            DemoClock.from_settings(settings),
            settings.demo_session_secret,
        ),
        provider,
        factory,
    )


@router.get("/operations/capabilities", response_model=OperationsCapabilities)
def capabilities(
    provider: Annotated[ProviderSettings, Depends(operations_settings)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationsCapabilities:
    return OperationsCapabilities(
        enabled=provider.enabled,
        external_processing=provider.enabled,
        providers=provider.active_providers,
        season_start=settings.demo_season_start,
        season_end=settings.demo_season_end,
    )


async def watch_disconnect(request: Request, cancelled: threading.Event) -> None:
    # FastAPI has already consumed/validated this endpoint's complete JSON body.
    # This is its only later receive consumer. Blocking receive crosses the
    # BaseHTTPMiddleware wrapper; Request.is_disconnected()'s pre-cancelled poll
    # can instead cancel at that wrapper's checkpoint before observing the server.
    while not cancelled.is_set():
        message = await request.receive()
        if message["type"] == "http.disconnect":
            cancelled.set()
            return


@router.post("/operations/review", response_model=OperationsReviewRead)
async def review_operations(
    payload: ReviewRequest,
    request: Request,
    service: Annotated[OperationsReviewService, Depends(operations_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationsReviewRead:
    started_at = monotonic()
    if not service.settings.enabled:
        raise review_error("agent_disabled", 503)
    # New read-POST still uses cookie authority; enforce same-origin even in local
    # development. QA must configure its actual loopback PUBLIC_BASE_URL explicitly.
    if request.headers.get("origin") != settings.public_base_url:
        raise review_error("origin_not_allowed", 403)
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise review_error("session_required", 401)
    if not _review_slots.acquire(blocking=False):
        raise review_error("review_busy", 429, 2)
    cancelled = threading.Event()

    def worker() -> OperationsReviewRead:
        try:
            return service.review(
                cookie,
                payload.selected_date,
                cancelled.is_set,
                started_at,
                request_id=request.state.request_id,
            )
        finally:
            # A cancelled HTTP waiter is not a stopped worker/provider request.
            _review_slots.release()

    work = asyncio.create_task(asyncio.to_thread(worker))

    # Retrieve any late exception after an HTTP disconnect/timeout without logging
    # raw exception values or returning an obsolete result to a different request.
    def consume(task: asyncio.Task[OperationsReviewRead]) -> None:
        if not task.cancelled():
            task.exception()

    work.add_done_callback(consume)
    watcher = asyncio.create_task(watch_disconnect(request, cancelled))
    try:
        return await asyncio.wait_for(
            asyncio.shield(work), timeout=service.settings.deadline_seconds
        )
    except TimeoutError:
        cancelled.set()
        raise review_error("timeout", 504) from None
    except asyncio.CancelledError:
        cancelled.set()
        raise
    except AgentFailure as error:
        status = error.http_status
        if error.code in {"session_required", "session_expired"}:
            status = 401
        elif error.code in {"date_out_of_range", "snapshot_too_large"}:
            status = 422
        raise review_error(error.code, status, error.retry_after_seconds) from None
    except Exception:
        logger.error("operations_review failed code=internal_failure")
        raise review_error("ai_temporarily_unavailable", 503) from None
    finally:
        cancelled.set()
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
