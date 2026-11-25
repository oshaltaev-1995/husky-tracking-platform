"""One fixed-origin TLS request with bounded reads and no redirect/retry machinery.

The synchronous system DNS resolver cannot be forcibly interrupted by stdlib.
Check the same deadline after connect and BEFORE sending HTTP, so late DNS/TLS
completion cannot dispatch a new request. The API owns its overall watchdog and
cooperative cancellation. Already dispatched remote generation is not refundable.
"""

from __future__ import annotations

import http.client
import socket
import ssl
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Protocol
from urllib.parse import urlsplit

from app.operations.diagnostics import FailureReason, annotate_failure, bounded_size
from app.operations.provider_models import AgentFailure, HttpReply, HttpRequest

ENDPOINTS = {
    "https://api.groq.com/openai/v1/chat/completions": (
        "api.groq.com",
        "/openai/v1/chat/completions",
    ),
    "https://openrouter.ai/api/v1/chat/completions": (
        "openrouter.ai",
        "/api/v1/chat/completions",
    ),
}


class TLSChannel(Protocol):
    def settimeout(self, value: float | None) -> None: ...
    def shutdown(self, how: int) -> None: ...


class Response(Protocol):
    status: int

    def getheader(self, name: str) -> str | None: ...
    def read1(self, n: int = -1) -> bytes: ...
    def close(self) -> None: ...


class Connection(Protocol):
    @property
    def sock(self) -> TLSChannel | None: ...

    def connect(self) -> None: ...
    def request(
        self,
        method: str,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> None: ...
    def getresponse(self) -> Response: ...
    def close(self) -> None: ...


class ConnectionFactory(Protocol):
    def __call__(
        self,
        host: str,
        timeout: float,
        context: ssl.SSLContext,
    ) -> Connection: ...


def tls_connection(host: str, timeout: float, context: ssl.SSLContext) -> Connection:
    return http.client.HTTPSConnection(host, timeout=timeout, context=context)


class HTTPSProviderTransport:
    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory = tls_connection,
        monotonic: Callable[[], float] = time.monotonic,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> None:
        self._factory = connection_factory
        self._clock = monotonic
        self._cancelled = cancelled

    def __call__(self, request: HttpRequest) -> HttpReply:
        if request.url not in ENDPOINTS or request.follow_redirects or request.retries:
            raise AgentFailure("provider_configuration")
        parsed = urlsplit(request.url)
        host, path = ENDPOINTS[request.url]
        if parsed.scheme != "https" or parsed.hostname != host or parsed.path != path:
            raise AgentFailure("provider_configuration")
        deadline = self._clock() + request.timeout_seconds
        expired = threading.Event()

        def remaining() -> float:
            if self._cancelled():
                raise AgentFailure("cancelled", http_status=409)
            value = deadline - self._clock()
            if value <= 0 or expired.is_set():
                raise AgentFailure("provider_timeout")
            return value

        metadata: dict[str, object] = {}
        connection: Connection | None = None
        response: Response | None = None
        timer: threading.Timer | None = None
        try:
            context = ssl.create_default_context()
            connection = self._factory(host, remaining(), context)
            connection.connect()
            channel = connection.sock
            if channel is None:
                raise AgentFailure("provider_transport")

            def interrupt() -> None:
                expired.set()
                # A completed/closing socket may already be gone.
                with suppress(OSError):
                    channel.shutdown(socket.SHUT_RDWR)

            # Socket timeouts alone restart at individual reads, so a slow stream
            # of headers could otherwise extend a call. This one-shot deadline
            # also interrupts getresponse()/read1() while they are blocked.
            timer = threading.Timer(remaining(), interrupt)
            timer.daemon = True
            timer.start()
            # Retain the actual TLS socket even if HTTPConnection hands it off to
            # a response with Connection:close; each blocking phase gets the
            # remaining whole-call budget, rather than restarting a read timeout.
            channel.settimeout(remaining())
            connection.request(
                "POST",
                path,
                request.body_json.encode(),
                {
                    "Authorization": request.authorization.get_secret_value(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            )
            channel.settimeout(remaining())
            response = connection.getresponse()
            if 100 <= response.status <= 599:
                metadata["upstream_http_status"] = response.status
            remaining()
            retry_after = response.getheader("Retry-After")
            if retry_after is not None and len(retry_after) > 100:
                retry_after = None
            if not 100 <= response.status <= 599:
                raise annotate_failure(
                    AgentFailure("invalid_provider_response", http_status=502),
                    "transport",
                    "transport_status",
                    **metadata,
                )
            if not 200 <= response.status < 300:
                # Error bodies are unnecessary for routing and could contain
                # provider internals. Close without reading/logging them.
                return HttpReply(status=response.status, retry_after=retry_after)
            encoding = response.getheader("Content-Encoding")
            if encoding not in {None, "identity"}:
                raise annotate_failure(
                    AgentFailure("invalid_provider_response", http_status=502),
                    "transport",
                    "transport_encoding",
                    **metadata,
                )
            length = response.getheader("Content-Length")
            expected_length = None
            if length is not None:
                if len(length) > 20 or not length.isascii() or not length.isdecimal():
                    raise annotate_failure(
                        AgentFailure("invalid_provider_response", http_status=502),
                        "transport",
                        "response_length",
                        **metadata,
                    )
                expected_length = int(length)
                if expected_length > request.response_limit_bytes:
                    # Declared bytes have not been read; do not report them as read.
                    raise annotate_failure(
                        AgentFailure("invalid_provider_response", http_status=502),
                        "transport",
                        "response_size",
                        **metadata,
                    )
            chunks = bytearray()
            while True:
                channel.settimeout(remaining())
                # At most cap+1 bytes enter memory; no unbounded response.read().
                part = response.read1(
                    min(4096, request.response_limit_bytes + 1 - len(chunks))
                )
                remaining()
                if not part:
                    break
                chunks.extend(part)
                metadata["response_bytes"] = bounded_size(len(chunks))
                if len(chunks) > request.response_limit_bytes:
                    raise annotate_failure(
                        AgentFailure("invalid_provider_response", http_status=502),
                        "transport",
                        "response_size",
                        **metadata,
                    )
            if expected_length is not None and len(chunks) != expected_length:
                raise annotate_failure(
                    AgentFailure("provider_transport"),
                    "transport",
                    "transport_fragmentation",
                    **metadata,
                )
            return HttpReply(
                status=response.status, body=bytes(chunks), retry_after=retry_after
            )
        except AgentFailure as error:
            if error.diagnostic is None:
                reason: FailureReason = (
                    "cancelled" if error.code == "cancelled" else "unknown"
                )
                if error.code == "provider_timeout":
                    reason = "transport_timeout"
                annotate_failure(error, "transport", reason, **metadata)
            raise
        except TimeoutError:
            raise annotate_failure(
                AgentFailure("provider_timeout"),
                "transport",
                "transport_timeout",
                **metadata,
            ) from None
        except (OSError, http.client.HTTPException):
            if expired.is_set():
                raise annotate_failure(
                    AgentFailure("provider_timeout"),
                    "transport",
                    "transport_timeout",
                    **metadata,
                ) from None
            raise annotate_failure(
                AgentFailure("provider_transport"),
                "transport",
                "transport_network",
                **metadata,
            ) from None
        except ValueError:
            # Includes rejected header values; no key or raw exception escapes.
            raise annotate_failure(
                AgentFailure("provider_configuration"),
                "transport",
                "transport_configuration",
                **metadata,
            ) from None
        finally:
            if timer is not None:
                timer.cancel()
            if response is not None:
                with suppress(OSError, http.client.HTTPException):
                    response.close()
            if connection is not None:
                with suppress(OSError, http.client.HTTPException):
                    connection.close()
