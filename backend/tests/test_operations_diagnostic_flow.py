"""Safe request/run correlation through the real HTTP/loop boundary; fake model only."""

from __future__ import annotations

import json
import re
from time import monotonic
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_operations_final import Model, Reader, config
from test_operations_tools import context_snapshot

from app.api.routes import operations as routes
from app.core.config import get_settings
from app.main import app
from app.operations import policy
from app.operations.provider_models import AgentFailure, HttpReply, HttpRequest
from app.operations.review import OperationsReviewService
from app.operations.snapshot import SnapshotReader

SENTINEL = "private-cookie-prompt-body-key-dog-name-DO-NOT-LOG"


def observations(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [
        json.loads(record.getMessage().split("operations_diagnostic ", 1)[1])
        for record in caplog.records
        if record.getMessage().startswith("operations_diagnostic ")
    ]


def test_real_request_id_correlates_two_phases_without_trusting_client_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = context_snapshot()
    model = Model(state)
    reader = Reader(state)
    service = OperationsReviewService(
        cast(SnapshotReader, reader), config(), lambda _: model
    )
    app.dependency_overrides[routes.operations_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/operations/review",
                json={"selected_date": "2026-03-29"},
                headers={
                    "origin": get_settings().public_base_url,
                    "cookie": "ht_demo_session=" + SENTINEL,
                    "x-request-id": SENTINEL,
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[a-f0-9]{32}", request_id)
    events = observations(caplog)
    assert [row["request_phase"] for row in events] == ["tool_review", "final_only"]
    assert [row["http_attempt"] for row in events] == [1, 2]
    assert [row["mandatory_validation_completed"] for row in events] == [False, True]
    assert [row["recorded_tools"] for row in events] == [0, 1]
    assert {row["request_id"] for row in events} == {request_id}
    assert len({row["run_id"] for row in events}) == 1
    assert events[0]["run_id"] != request_id
    assert all(row["upstream_http_status"] == 200 for row in events)
    assert (
        not {"failure_stage", "failure_reason", "diagnostics"} & response.json().keys()
    )
    assert SENTINEL not in caplog.text + response.text + repr(service)
    assert reader.captures == 1


@pytest.mark.parametrize(
    "mode,reason,status",
    [
        ("json", "content_json", 502),
        ("schema", "final_schema", 422),
        ("membership", "reference_membership", 422),
        ("length", "finish_length", 502),
    ],
)
def test_failure_keeps_safe_response_metadata_until_private_log(
    mode: str,
    reason: str,
    status: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = context_snapshot()
    model = Model(state)
    reader = Reader(state)
    if mode == "schema":
        model.final_mutation = lambda value: value.update(explanation=42)
    if mode == "membership":
        model.final_mutation = lambda value: value.update(observation_ids=[SENTINEL])

    def transport(request: HttpRequest) -> HttpReply:
        reply = model(request)
        if len(model.calls) != 2 or mode not in {"json", "length"}:
            return reply
        value = json.loads(reply.body)
        value["choices"][0]["message"]["content"] = SENTINEL
        if mode == "length":
            value["choices"][0]["finish_reason"] = "length"
        return HttpReply(status=200, body=json.dumps(value).encode())

    service = OperationsReviewService(
        cast(SnapshotReader, reader), config(), lambda _: transport
    )
    with pytest.raises(AgentFailure) as caught:
        service.review(
            SENTINEL,
            state.selected_date,
            lambda: False,
            monotonic(),
            request_id="a" * 32,
        )
    assert caught.value.http_status == status
    event = observations(caplog)[-1]
    assert event["failure_reason"] == reason
    assert event["request_phase"] == "final_only" and event["http_attempt"] == 2
    assert event["upstream_http_status"] == 200
    assert event["response_bytes"] and event["content_bytes"]
    assert event["mandatory_validation_completed"] is True
    assert event["recorded_tools"] == 1
    assert SENTINEL not in caplog.text + repr(caught.value)
    assert len(model.calls) == 2


def test_broken_diagnostic_instrumentation_cannot_break_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = context_snapshot()
    model = Model(state)
    reader = Reader(state)

    def broken(**_: object) -> None:
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(policy, "safe_diagnostic", broken)
    service = OperationsReviewService(
        cast(SnapshotReader, reader), config(), lambda _: model
    )
    result = service.review(SENTINEL, state.selected_date, lambda: False, monotonic())
    assert result.http_calls == 2 and result.presentation.status == "ready"
    assert SENTINEL not in result.model_dump_json()


def test_terminal_attempt_fence_does_not_erase_completed_validation_fact() -> None:
    from test_operations_rate_recovery import (
        Clock,
        Transport,
        active,
        tool,
        validate_once,
    )

    run = active(Transport(tool()), Clock(), max_http_calls=1)
    validate_once(run)
    with pytest.raises(AgentFailure, match="run_budget_exhausted"):
        run.call()
    event = run.diagnostics[-1]
    assert event["request_phase"] == "final_only"
    assert event["mandatory_validation_completed"] is True
    assert event["recorded_tools"] == 1 and event["http_attempt"] == 1
    assert event["failure_reason"] == "budget"


def test_broken_diagnostics_cannot_replace_original_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_operations_rate_recovery import Clock, Transport, active

    def broken(**_: object) -> None:
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(policy, "safe_diagnostic", broken)
    run = active(Transport(OSError(SENTINEL)), Clock())
    with pytest.raises(AgentFailure, match="^ai_temporarily_unavailable$"):
        run.call()
    assert run.http_calls == 1
