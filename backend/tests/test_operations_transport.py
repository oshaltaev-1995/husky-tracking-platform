"""Injected connections only: no DNS, socket connection or paid provider request."""

from __future__ import annotations

import http.client
import socket
import ssl
import threading
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from app.operations.http_transport import HTTPSProviderTransport
from app.operations.provider_models import (
    AgentFailure,
    HttpRequest,
    get_provider_settings,
)


class FakeChannel:
    def __init__(self) -> None:
        self.timeouts: list[float | None] = []
        self.interrupted = threading.Event()

    def settimeout(self, value: float | None) -> None:
        self.timeouts.append(value)

    def shutdown(self, how: int) -> None:
        assert how == socket.SHUT_RDWR
        self.interrupted.set()


class FakeResponse:
    def __init__(
        self,
        body: bytes = b'{"value":1}',
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status, self.body = status, body
        self.headers = headers or {}
        self.closed = False
        self.read_sizes: list[int] = []

    def getheader(self, name: str) -> str | None:
        return self.headers.get(name)

    def read1(self, n: int = -1) -> bytes:
        assert 0 < n <= 4096
        self.read_sizes.append(n)
        part, self.body = self.body[:n], self.body[n:]
        return part

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, response: FakeResponse) -> None:
        self.sock = FakeChannel()
        self.response = response
        self.connected = False
        self.closed = False
        self.requests: list[tuple[str, str, bytes, dict[str, str]]] = []

    def connect(self) -> None:
        self.connected = True

    def request(
        self,
        method: str,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        self.requests.append((method, url, body, headers))

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def request(**updates: Any) -> HttpRequest:
    return HttpRequest(
        url=updates.pop("url", "https://api.groq.com/openai/v1/chat/completions"),
        authorization=SecretStr("Bearer strictly-offline-secret"),
        body_json="{}",
        timeout_seconds=updates.pop("timeout_seconds", 2.0),
        response_limit_bytes=updates.pop("response_limit_bytes", 1024),
        **updates,
    )


def transport(connection: FakeConnection, **kwargs: Any) -> HTTPSProviderTransport:
    def factory(host: str, timeout: float, context: ssl.SSLContext) -> FakeConnection:
        assert host in {"api.groq.com", "openrouter.ai"}
        assert 0 < timeout <= 2
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        return connection

    return HTTPSProviderTransport(connection_factory=factory, **kwargs)


def test_tls_one_request_bounded_reads_and_close_without_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reply = FakeResponse(b"x" * 1000, headers={"Content-Length": "1000"})
    connection = FakeConnection(reply)
    result = transport(connection)(request())
    assert result.body == b"x" * 1000 and result.status == 200
    assert connection.connected and connection.closed and reply.closed
    assert len(connection.requests) == 1
    method, path, _, headers = connection.requests[0]
    assert (method, path) == ("POST", "/openai/v1/chat/completions")
    assert headers["Accept-Encoding"] == "identity"
    assert headers["Authorization"] == "Bearer strictly-offline-secret"
    assert max(reply.read_sizes) <= 1025
    assert all(0 < value <= 2 for value in connection.sock.timeouts)
    assert "strictly-offline-secret" not in caplog.text
    assert "strictly-offline-secret" not in repr(request())


@pytest.mark.parametrize("status", [302, 307, 401, 402, 403, 429, 500])
def test_error_and_redirect_bodies_are_not_loaded_or_followed(status: int) -> None:
    reply = FakeResponse(
        b"do-not-load" * 10000,
        status=status,
        headers={
            "Location": "https://untrusted.invalid",
            "Retry-After": "60",
        },
    )
    connection = FakeConnection(reply)
    result = transport(connection)(request())
    assert result.status == status and result.retry_after == "60" and result.body == b""
    assert reply.read_sizes == [] and len(connection.requests) == 1
    assert connection.closed and reply.closed


def test_chunked_or_missing_length_can_read_only_cap_plus_one() -> None:
    reply = FakeResponse(b"x" * 1_000_000)
    connection = FakeConnection(reply)
    with pytest.raises(AgentFailure, match="^invalid_provider_response$"):
        transport(connection)(request())
    assert len(reply.body) == 1_000_000 - 1025
    assert reply.read_sizes == [1025]
    assert connection.closed and reply.closed


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Length": "1025"},
        {"Content-Length": "9" * 5000},
        {"Content-Length": "not-a-number"},
        {"Content-Encoding": "gzip"},
    ],
)
def test_unacceptable_body_headers_fail_before_any_read(
    headers: dict[str, str],
) -> None:
    reply = FakeResponse(headers=headers)
    connection = FakeConnection(reply)
    with pytest.raises(AgentFailure, match="^invalid_provider_response$"):
        transport(connection)(request())
    assert reply.read_sizes == [] and connection.closed and reply.closed


def test_truncated_declared_length_is_transport_failure() -> None:
    connection = FakeConnection(FakeResponse(b"{}", headers={"Content-Length": "10"}))
    with pytest.raises(AgentFailure, match="^provider_transport$"):
        transport(connection)(request())


@pytest.mark.parametrize(
    "exception,code",
    [
        (TimeoutError("private transport detail"), "provider_timeout"),
        (OSError("private transport detail"), "provider_transport"),
        (
            ssl.SSLCertVerificationError("private transport detail"),
            "provider_transport",
        ),
        (http.client.BadStatusLine("private transport detail"), "provider_transport"),
        (ValueError("private header credential"), "provider_configuration"),
    ],
)
def test_non_os_http_errors_are_typed_and_no_raw_detail_is_exposed(
    exception: Exception,
    code: str,
) -> None:
    connection = FakeConnection(FakeResponse())

    def fail() -> FakeResponse:
        raise exception

    connection.getresponse = fail
    with pytest.raises(AgentFailure) as caught:
        transport(connection)(request())
    assert caught.value.code == code and str(caught.value) == code
    assert "private" not in str(caught.value) and connection.closed


def test_late_dns_connect_cannot_send_http_after_call_deadline() -> None:
    clock = [0.0]
    connection = FakeConnection(FakeResponse())

    def late_connect() -> None:
        clock[0] = 2.0

    connection.connect = late_connect
    with pytest.raises(AgentFailure, match="^provider_timeout$"):
        transport(connection, monotonic=lambda: clock[0])(request())
    assert not connection.requests and connection.closed


def test_cancel_during_connect_does_not_send_http() -> None:
    cancelled = [False]
    connection = FakeConnection(FakeResponse())

    def cancel() -> None:
        cancelled[0] = True

    connection.connect = cancel
    with pytest.raises(AgentFailure, match="^cancelled$"):
        transport(connection, cancelled=lambda: cancelled[0])(request())
    assert not connection.requests and connection.closed


def test_whole_body_deadline_is_not_reset_for_each_chunk() -> None:
    clock = [0.0]
    connection = FakeConnection(FakeResponse(b"abc"))

    def drip(n: int) -> bytes:
        clock[0] += 1.1
        return b"x"

    connection.response.read1 = drip
    with pytest.raises(AgentFailure, match="^provider_timeout$"):
        transport(connection, monotonic=lambda: clock[0])(request())
    assert connection.closed and connection.response.closed
    assert connection.sock.timeouts[-1] < 1


def test_absolute_timer_interrupts_a_stalled_header_read() -> None:
    connection = FakeConnection(FakeResponse())

    def blocked_header() -> FakeResponse:
        assert connection.sock.interrupted.wait(timeout=0.5)
        raise OSError("interrupted after deadline")

    connection.getresponse = blocked_header
    with pytest.raises(AgentFailure, match="^provider_timeout$"):
        transport(connection)(request(timeout_seconds=0.03))
    assert connection.sock.interrupted.is_set() and connection.closed


def test_unknown_host_and_unsafe_flags_fail_before_connection() -> None:
    connection = FakeConnection(FakeResponse())
    invalid = request().model_copy(update={"url": "https://untrusted.invalid/"})
    with pytest.raises(AgentFailure, match="^provider_configuration$"):
        transport(connection)(invalid)
    assert not connection.connected


def test_explicit_private_agent_settings_file_and_no_implicit_search(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in ("AGENT_ENABLED", "AGENT_ENV_FILE", "AGENT_GROQ_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "AGENT_ENABLED=true\nAGENT_GROQ_API_KEY=wrong-project\n"
    )
    monkeypatch.chdir(tmp_path)
    assert get_provider_settings().enabled is False
    private = tmp_path / "agent config.env"
    private.write_text("AGENT_ENABLED=true\nAGENT_GROQ_API_KEY=offline-project-key\n")
    private.chmod(0o600)
    monkeypatch.setenv("AGENT_ENV_FILE", str(private))
    settings = get_provider_settings()
    assert settings.enabled is True
    assert settings.groq_api_key.get_secret_value() == "offline-project-key"
    assert "offline-project-key" not in repr(settings)


@pytest.mark.parametrize("failure", ["missing", "public", "invalid"])
def test_explicit_agent_file_errors_are_redacted(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Runtime env intentionally takes precedence over the operator-selected file.
    # Isolate the malformed file case from the offline harness's disabled flag.
    monkeypatch.delenv("AGENT_ENABLED", raising=False)
    private = tmp_path / "private.env"
    monkeypatch.setenv("AGENT_ENV_FILE", str(private))
    if failure != "missing":
        private.write_text("AGENT_ENABLED=not-valid-secret-text\n")
        private.chmod(0o644 if failure == "public" else 0o600)
    with pytest.raises(AgentFailure, match="^provider_configuration$") as caught:
        get_provider_settings()
    assert "secret" not in str(caught.value)
