"""Real PostgreSQL API/loop tests with fake model responses, never live inference."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Event
from time import monotonic
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, func, select

from app.api.routes import demo_workspace as privacy_routes
from app.api.routes import operations as routes
from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.catalog import EXPECTED_SEMANTIC_CHECKSUM
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.main import app
from app.models import (
    DailyPlan,
    DemoWorkspace,
    DemoWorkspaceDay,
    DemoWorkspaceHousingOverride,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)
from app.operations.provider_models import HttpReply, HttpRequest, ProviderSettings
from app.operations.schemas import OperationError
from app.operations.snapshot import SnapshotReader
from app.operations.tools import FrozenTools
from app.services.demo_workspace_service import resolve_workspace

REVIEW = "/api/v1/operations/review"
DAY = "2026-03-29"


def clock() -> DemoClock:
    return DemoClock.from_settings(get_settings())


@pytest.fixture(autouse=True)
def disposable_world() -> Iterator[None]:
    if os.environ.get("P13F_DISPOSABLE_DB_CONFIRMED") != "1":
        pytest.skip("Requires the positively identified disposable PostgreSQL")
    assert engine.url.get_backend_name() == "postgresql"
    assert engine.url.host == "127.0.0.1" and engine.url.database == "husky_tracking"
    with SessionLocal.begin() as session:
        reset_demo_world(session, clock(), require_enabled=False)
    yield
    app.dependency_overrides.clear()
    # A cancelled waiter is not proof that its worker ended. Every test transport
    # is bounded/released in finally; refuse to leak a slot into another test.
    until = monotonic() + 3
    while monotonic() < until:
        if routes._review_slots.acquire(blocking=False):
            routes._review_slots.release()
            break
        Event().wait(0.01)
    else:
        raise AssertionError("A review worker did not finish")


def settings(**changes: Any) -> ProviderSettings:
    return ProviderSettings(
        enabled=True,
        groq_free_account_confirmed=True,
        groq_api_key=SecretStr("offline-primary"),
        openrouter_api_key=SecretStr("offline-reserve"),
        **changes,
    )


def visitor(*, initialize: bool = True) -> TestClient:
    client = TestClient(app, headers={"Origin": get_settings().public_base_url})
    if initialize:
        assert client.get("/api/v1/demo/session").status_code == 200
    return client


def workspace(client: TestClient) -> int:
    with SessionLocal() as session:
        row = resolve_workspace(
            session,
            client.cookies.get("ht_demo_session"),
            get_settings().demo_session_secret,
        )
        assert row is not None
        return row.id


def counts() -> dict[str, int | None]:
    with SessionLocal() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                DemoWorkspace,
                DemoWorkspaceDay,
                DemoWorkspaceHousingOverride,
                DailyPlan,
                PlannedActivity,
                PlannedActivityParticipant,
                PlannedTeam,
                PlannedTeamSlot,
                WorkSession,
                WorkParticipation,
            )
        }


class FakeModel:
    def __init__(self, mode: str = "normal") -> None:
        self.mode = mode
        self.calls: list[HttpRequest] = []
        self.pending = Event()
        self.release = Event()
        self.finished = Event()

    def __call__(self, request: HttpRequest) -> HttpReply:
        self.calls.append(request)
        if self.mode == "blocked":
            self.pending.set()
            try:
                assert self.release.wait(3)
            finally:
                self.finished.set()
        if self.mode == "quota":
            return HttpReply(status=429, retry_after="4")
        if self.mode == "transport":
            raise OSError("not logged: fixture-provider-body")
        if self.mode.startswith("status-"):
            return HttpReply(
                status=int(self.mode.split("-")[1]), body=b"private-provider-body"
            )
        if self.mode == "invalid-json":
            return HttpReply(status=200, body=b"private-provider-body")
        body = json.loads(request.body_json)
        snapshot = json.loads(body["messages"][2]["content"].split("\n", 1)[1])
        on_reserve = "openrouter" in request.url
        had_tool = any(message["role"] == "tool" for message in body["messages"])
        if self.mode == "midrun" and not on_reserve and had_tool:
            return HttpReply(status=429, retry_after="2")
        if (
            not had_tool and self.mode != "premature-final"
        ) or self.mode == "tool-loop":
            name = "execute_sql" if self.mode == "forbidden-tool" else "validate_day"
            args = {"selected_date": snapshot["selected_date"]}
            if self.mode == "invalid-arguments":
                args["workspace_id"] = "not authorization"
            message = {
                "content": None,
                "tool_calls": [
                    {
                        "id": "step-1",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            }
            finish = "tool_calls"
        else:
            explanation = (
                "<img src=x onerror=alert(1)> "
                "Planned work is not confirmed actual work."
            )
            reference = {
                "snapshot_id": snapshot["snapshot_id"],
                "selected_date": snapshot["selected_date"],
                "evidence_id": "invented"
                if self.mode == "invalid-evidence"
                else "e-001",
                "entity": {"kind": "day", "id": snapshot["selected_date"]},
            }
            message = {
                "content": json.dumps(
                    {"explanation": explanation, "references": [reference]}
                ),
                "reasoning": "secret-reasoning-sentinel",
            }
            finish = "stop"
        return HttpReply(
            status=200,
            body=json.dumps(
                {
                    "choices": [{"finish_reason": finish, "message": message}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                }
            ).encode(),
        )


def install(model: FakeModel, configuration: ProviderSettings | None = None) -> None:
    app.dependency_overrides[routes.operations_settings] = lambda: (
        configuration or settings()
    )
    app.dependency_overrides[routes.operations_transport_factory] = lambda: (
        lambda _: model
    )


def test_public_capabilities_privacy_and_disabled_review_create_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel()
    disabled = ProviderSettings(enabled=False)
    install(model, disabled)
    monkeypatch.setattr(privacy_routes, "get_provider_settings", lambda: disabled)
    client = visitor(initialize=False)
    before = counts()
    capability = client.get("/api/v1/operations/capabilities")
    assert capability.status_code == 200
    assert (
        capability.json()["enabled"] is False and capability.json()["providers"] == []
    )
    metadata = client.get("/api/v1/public/privacy")
    assert (
        metadata.status_code == 200
        and metadata.json()["operations_review_enabled"] is False
        and metadata.json()["operations_review_providers"] == []
    )
    assert (
        client.post(REVIEW, json={"selected_date": DAY}).json()["detail"]["code"]
        == "agent_disabled"
    )
    assert counts() == before and not client.cookies and not model.calls
    assert (
        "set-cookie" not in capability.headers and "set-cookie" not in metadata.headers
    )


@pytest.mark.parametrize(
    "extra", ["workspace_id", "prompt", "model", "url", "tools", "settings"]
)
def test_request_contract_rejects_extra_fields_without_echo_or_provider(
    extra: str,
) -> None:
    model = FakeModel()
    install(model)
    client = visitor()
    before = counts()
    response = client.post(
        REVIEW, json={"selected_date": DAY, extra: "do-not-echo-sentinel"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_review_request"
    assert "do-not-echo-sentinel" not in response.text
    assert not model.calls and counts() == before


@pytest.mark.parametrize("value", ["2026-3-29", "2026-03-29T00:00:00", 20260329, True])
def test_request_contract_accepts_only_iso_calendar_dates(value: object) -> None:
    model = FakeModel()
    install(model)
    response = visitor().post(REVIEW, json={"selected_date": value})
    assert response.status_code == 422 and not model.calls


@pytest.mark.parametrize("when", ["2025-11-30", "2026-04-01"])
def test_out_of_season_date_refuses_without_dispatch(when: str) -> None:
    model = FakeModel()
    install(model)
    response = visitor().post(REVIEW, json={"selected_date": when})
    assert (
        response.status_code == 422
        and response.json()["detail"]["code"] == "date_out_of_range"
    )
    assert not model.calls


@pytest.mark.parametrize("reserve_enabled", [False, True])
def test_enabled_capabilities_and_privacy_expose_only_processing_metadata(
    monkeypatch: pytest.MonkeyPatch,
    reserve_enabled: bool,
) -> None:
    model = FakeModel()
    configuration = settings(openrouter_reserve_enabled=reserve_enabled)
    install(model, configuration)
    monkeypatch.setattr(privacy_routes, "get_provider_settings", lambda: configuration)
    client = visitor(initialize=False)
    before = counts()
    metadata = client.get("/api/v1/public/privacy")
    capability = client.get("/api/v1/operations/capabilities")
    assert metadata.json()["operations_review_enabled"] is True
    expected_providers = ["groq", "openrouter"] if reserve_enabled else ["groq"]
    assert capability.json()["providers"] == expected_providers
    assert metadata.json()["operations_review_providers"] == expected_providers
    assert capability.json()["external_processing"] is True
    assert "offline-primary" not in capability.text + metadata.text
    assert "offline-reserve" not in capability.text + metadata.text
    assert not client.cookies and not model.calls and counts() == before


def test_no_cookie_expiry_and_foreign_origin_do_not_create_or_replace_sessions() -> (
    None
):
    model = FakeModel()
    install(model)
    missing = visitor(initialize=False)
    before = counts()
    response = missing.post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == 401 and "set-cookie" not in response.headers
    assert counts() == before
    client = visitor()
    own = workspace(client)
    bad_origin = client.post(
        REVIEW,
        json={"selected_date": DAY},
        headers={"Origin": "https://foreign.example"},
    )
    assert bad_origin.status_code == 403
    with SessionLocal.begin() as session:
        session.get(DemoWorkspace, own).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    response = client.post(REVIEW, json={"selected_date": DAY})
    assert (
        response.status_code == 401
        and response.json()["detail"]["code"] == "session_expired"
    )
    assert "set-cookie" not in response.headers and not model.calls


@pytest.mark.parametrize("when", ["2025-12-01", DAY, "2026-03-31"])
def test_complete_model_tool_final_api_flow_is_read_only_and_has_safe_evidence(
    when: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model = FakeModel()
    install(model)
    client = visitor()
    before = counts()
    writes: list[bool] = []

    def flush(*_: object) -> None:
        writes.append(True)

    event.listen(SessionLocal.class_, "before_flush", flush)
    try:
        response = client.post(REVIEW, json={"selected_date": when})
    finally:
        event.remove(SessionLocal.class_, "before_flush", flush)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["selected_date"] == when and result["captured_at"]
    assert result["provider"] == "groq" and result["fallback"] is False
    assert result["http_calls"] == 2 and result["tool_calls"] == 1
    assert result["trace"][0]["tool_name"] == "validate_day"
    assert {row["rule"] for row in result["facts"]} == {
        "PLAN_PRESENCE",
        "ACTUAL_LEDGER",
    }
    assert all(row["selected_date"] == when for row in result["evidence"])
    assert all(row["path"].startswith("/demo/") for row in result["links"])
    assert result["explanation"].startswith("<img")  # Text; never trusted HTML.
    assert (
        "secret-reasoning-sentinel" not in response.text
        and "secret-reasoning-sentinel" not in caplog.text
    )
    assert result["usage"] == {
        "known_prompt_tokens": 20,
        "known_completion_tokens": 8,
        "incomplete": False,
    }
    assert (
        response.headers["cache-control"] == "no-store"
        and "set-cookie" not in response.headers
    )
    assert counts() == before and not writes
    with SessionLocal() as session:
        assert semantic_checksum(session) == EXPECTED_SEMANTIC_CHECKSUM


def test_midrun_restart_uses_same_snapshot_without_primary_transcript_or_writes() -> (
    None
):
    model = FakeModel("midrun")
    install(model, settings(openrouter_reserve_enabled=True))
    client = visitor()
    before = counts()
    response = client.post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider"] == "openrouter" and result["fallback"] is True
    assert (result["http_calls"], result["tool_calls"]) == (4, 2)
    assert result["usage"]["known_prompt_tokens"] == 30
    assert result["usage"]["incomplete"] is True
    bodies = [json.loads(call.body_json) for call in model.calls]
    assert bodies[0]["messages"] == bodies[2]["messages"]
    assert len(bodies[1]["messages"]) > len(bodies[2]["messages"])
    assert [row["provider"] for row in result["trace"]] == ["groq", "openrouter"]
    assert counts() == before


@pytest.mark.parametrize(
    ("mode", "status", "code", "calls"),
    [
        ("quota", 429, "ai_quota_exhausted", 1),
        ("transport", 503, "ai_temporarily_unavailable", 1),
        ("status-401", 503, "provider_authentication", 1),
        ("status-403", 503, "provider_access_denied", 1),
        ("status-402", 503, "provider_payment_required", 1),
        ("invalid-json", 502, "invalid_provider_response", 1),
        ("forbidden-tool", 422, "forbidden_tool", 1),
        ("invalid-arguments", 422, "invalid_provider_response", 1),
        ("invalid-evidence", 422, "invalid_evidence", 2),
        ("premature-final", 502, "invalid_provider_response", 1),
        ("tool-loop", 429, "run_budget_exhausted", 6),
    ],
)
def test_loop_failures_are_typed_safe_and_not_safety_bypassed(
    mode: str,
    status: int,
    code: str,
    calls: int | None,
) -> None:
    model = FakeModel(mode)
    install(model)
    client = visitor()
    before = counts()
    response = client.post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == status, response.text
    assert response.json()["detail"]["code"] == code
    assert "private-provider-body" not in response.text
    if calls is None:
        # Repeated tools may hit the cumulative payload bound before HTTP count.
        assert 1 <= len(model.calls) <= 6
    else:
        assert len(model.calls) == calls
    assert counts() == before
    if mode == "quota":
        assert response.headers["retry-after"] == "4"
        assert "both" not in response.json()["detail"]["message"].lower()
        assert "daily" not in response.json()["detail"]["message"].lower()


@pytest.mark.parametrize(
    ("internal", "status", "public"),
    [
        ("timeout", 504, "timeout"),
        ("database_unavailable", 503, "ai_temporarily_unavailable"),
    ],
)
def test_capture_dependency_errors_are_safe_and_never_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    internal: str,
    status: int,
    public: str,
) -> None:
    model = FakeModel()
    install(model)

    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise OperationError(internal)

    monkeypatch.setattr(SnapshotReader, "capture", unavailable)
    response = visitor().post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == public
    assert not model.calls and "set-cookie" not in response.headers


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [("reset", 409, "context_changed"), ("expiry", 401, "session_expired")],
)
def test_context_invalidation_after_tool_prevents_followup_model_step(
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    status: int,
    code: str,
) -> None:
    model = FakeModel()
    install(model)
    client = visitor()
    own = workspace(client)
    original = FrozenTools.execute

    def after_tool(self: FrozenTools, name: str, arguments: str):
        result = original(self, name, arguments)
        if change == "reset":
            assert client.post("/api/v1/demo/reset").status_code == 200
        else:
            with SessionLocal.begin() as session:
                session.get(DemoWorkspace, own).expires_at = datetime.now(
                    UTC
                ) - timedelta(seconds=1)
        return result

    monkeypatch.setattr(FrozenTools, "execute", after_tool)
    response = client.post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == status and response.json()["detail"]["code"] == code
    assert len(model.calls) == 1 and "explanation" not in response.json()


def test_worker_limit_does_not_block_health_or_release_on_cancelled_waiter() -> None:
    model = FakeModel("blocked")
    install(model)
    with visitor() as client, ThreadPoolExecutor(max_workers=1) as pool:
        own = workspace(client)
        first = pool.submit(client.post, REVIEW, json={"selected_date": DAY})
        assert model.pending.wait(2)
        try:
            started = monotonic()
            assert client.get("/api/v1/health").status_code == 200
            assert monotonic() - started < 1
            # The snapshot transaction/lock is closed before a provider wait.
            with SessionLocal.begin() as session:
                assert (
                    session.scalar(
                        select(DemoWorkspace)
                        .where(DemoWorkspace.id == own)
                        .with_for_update(nowait=True)
                    )
                    is not None
                )
            other = client.post(REVIEW, json={"selected_date": DAY})
            assert (
                other.status_code == 429
                and other.json()["detail"]["code"] == "review_busy"
            )
            assert len(model.calls) == 1
        finally:
            model.release.set()
        assert first.result(timeout=3).status_code == 200


def test_disconnect_cancels_followup_and_discards_late_model_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel("blocked")
    install(model)

    async def disconnect_after_dispatch(_request: object, cancelled: Event) -> None:
        while not model.pending.is_set():
            await asyncio.sleep(0.01)
        cancelled.set()
        model.release.set()

    monkeypatch.setattr(routes, "watch_disconnect", disconnect_after_dispatch)
    response = visitor().post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "cancelled"
    assert len(model.calls) == 1 and "explanation" not in response.json()


def test_real_middleware_disconnect_stops_followup_model_dispatch() -> None:
    """Cross the real BaseHTTPMiddleware receive wrapper, without a fake watcher."""
    model = FakeModel()
    install(model)
    dispatched, observed = Event(), Event()

    def factory(cancelled):
        def transport(request: HttpRequest) -> HttpReply:
            if not model.calls:
                dispatched.set()
                until = monotonic() + 2
                while not cancelled() and monotonic() < until:
                    Event().wait(0.01)
                if cancelled():
                    observed.set()
            return model(request)

        return transport

    app.dependency_overrides[routes.operations_transport_factory] = lambda: factory
    client = visitor()
    cookie = client.cookies.get("ht_demo_session")

    async def scenario() -> list[dict[str, Any]]:
        incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        incoming.put_nowait(
            {
                "type": "http.request",
                "body": json.dumps({"selected_date": DAY}).encode(),
                "more_body": False,
            }
        )
        sent: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "scheme": "http",
            "method": "POST",
            "path": REVIEW,
            "raw_path": REVIEW.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"origin", get_settings().public_base_url.encode()),
                (b"cookie", f"ht_demo_session={cookie}".encode()),
                (b"content-type", b"application/json"),
            ],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
        task = asyncio.create_task(app(scope, incoming.get, send))
        try:
            assert await asyncio.to_thread(dispatched.wait, 2)
            incoming.put_nowait({"type": "http.disconnect"})
            assert await asyncio.to_thread(observed.wait, 2)
            await asyncio.wait_for(task, timeout=2)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        return sent

    sent = asyncio.run(scenario())
    assert len(model.calls) == 1
    assert (
        next(row["status"] for row in sent if row["type"] == "http.response.start")
        == 409
    )
    assert (
        "explanation"
        not in b"".join(
            row.get("body", b"") for row in sent if row["type"] == "http.response.body"
        ).decode()
    )


def test_outer_deadline_cancels_followup_and_keeps_slot_until_worker_finishes() -> None:
    model = FakeModel("blocked")
    install(model, settings(deadline_seconds=1.0))
    with visitor() as client:
        try:
            response = client.post(REVIEW, json={"selected_date": DAY})
            assert (
                response.status_code == 504
                and response.json()["detail"]["code"] == "timeout"
            )
            assert model.pending.is_set() and len(model.calls) == 1
            other = client.post(REVIEW, json={"selected_date": DAY})
            assert (
                other.status_code == 429
                and other.json()["detail"]["code"] == "review_busy"
            )
        finally:
            model.release.set()
            assert model.finished.wait(2)


def test_snapshot_lock_wait_is_bounded_by_remaining_deadline() -> None:
    client = visitor()
    own = workspace(client)
    reader = SnapshotReader(SessionLocal, clock(), get_settings().demo_session_secret)
    with SessionLocal.begin() as holder:
        holder.scalar(
            select(DemoWorkspace).where(DemoWorkspace.id == own).with_for_update()
        )
        started = monotonic()
        with pytest.raises(OperationError, match="timeout"):
            reader.capture(
                client.cookies.get("ht_demo_session"),
                date.fromisoformat(DAY),
                deadline=started + 0.1,
            )
        assert monotonic() - started < 1


def test_two_workspaces_remain_isolated_and_notes_never_enter_model_requests() -> None:
    first, second = visitor(), visitor()
    note = "private-free-text-not-for-model"
    assert (
        first.put(
            f"/api/v1/daily-plans/{DAY}",
            json={"notes": note, "expected_revision": None},
        ).status_code
        == 200
    )
    model = FakeModel()
    install(model)
    before = counts()
    a = first.post(REVIEW, json={"selected_date": DAY})
    b = second.post(REVIEW, json={"selected_date": DAY})
    assert a.status_code == b.status_code == 200
    assert a.json()["snapshot_id"] != b.json()["snapshot_id"]
    assert any(
        row["rule"] == "PLAN_PRESENCE" and row["status"] == "attention"
        for row in b.json()["findings"]
    )
    assert not any(
        row["rule"] == "PLAN_PRESENCE" and row["status"] == "attention"
        for row in a.json()["findings"]
    )
    assert all(note not in request.body_json for request in model.calls)
    assert all(
        first.cookies.get("ht_demo_session") not in request.body_json
        for request in model.calls
    )
    assert counts() == before


def test_short_after_tool_quota_retry_is_counted_once_in_same_read_only_review() -> (
    None
):
    class ShortQuotaModel(FakeModel):
        sent_quota = False

        def __call__(self, request: HttpRequest) -> HttpReply:
            body = json.loads(request.body_json)
            after_tool = any(row["role"] == "tool" for row in body["messages"])
            if after_tool and not self.sent_quota:
                self.sent_quota = True
                self.calls.append(request)
                return HttpReply(status=429, retry_after="1")
            return super().__call__(request)

    model = ShortQuotaModel()
    install(model)
    client = visitor()
    before = counts()
    response = client.post(REVIEW, json={"selected_date": DAY})
    assert response.status_code == 200
    result = response.json()
    assert result["quota_retries"] == 1 and result["http_calls"] == 3
    assert result["tool_calls"] == 1 and len(result["trace"]) == 1
    assert result["usage"]["incomplete"] is True
    assert len(model.calls) == 3
    assert model.calls[1].body_json == model.calls[2].body_json
    assert model.calls[1].url == model.calls[2].url
    assert counts() == before
