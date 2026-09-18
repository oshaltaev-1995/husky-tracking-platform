from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.services.demo_workspace_service import COOKIE_NAME

logger = logging.getLogger("uvicorn.error")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or get_settings()
    logging.getLogger().setLevel(active.log_level)
    application = FastAPI(
        title=active.app_name,
        version=active.app_version,
        docs_url=None if active.app_env == "production" else "/api/docs",
        redoc_url=None if active.app_env == "production" else "/api/redoc",
        openapi_url=None if active.app_env == "production" else "/api/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=active.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "If-Match", "X-Requested-With"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=active.allowed_hosts,
    )

    @application.middleware("http")
    async def production_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        if (
            active.demo_origin_check_enabled
            and request.method in UNSAFE_METHODS
            and COOKIE_NAME in request.cookies
            and request.headers.get("origin") != active.public_base_url
        ):
            response: Response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Request origin is not allowed"},
            )
        else:
            response = await call_next(request)
        if request.url.path.startswith(active.api_v1_prefix):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        response.headers["X-Request-ID"] = request_id
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    application.include_router(api_router, prefix=active.api_v1_prefix)
    return application


app = create_app()
