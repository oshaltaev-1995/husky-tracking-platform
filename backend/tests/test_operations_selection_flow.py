"""Full observation-selection lifecycle over frozen tools; fake HTTP/time only."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import SecretStr
from test_operations_rate_recovery import Clock
from test_operations_tools import context_snapshot

from app.operations.foundation import PreparedReview
from app.operations.policy import ProviderRun
from app.operations.provider_models import (
    AgentFailure,
    HttpReply,
    HttpRequest,
    ProviderSettings,
    ToolContract,
)
from app.operations.snapshot import RunContext
from app.operations.tools import FrozenTools


class Model:
    def __init__(self, quota: bool = False, extras: dict[str, object] | None = None):
        self.calls: list[HttpRequest] = []
        self.quota = quota
        self.extras = extras or {}

    def __call__(self, request: HttpRequest) -> HttpReply:
        self.calls.append(request)
        body = json.loads(request.body_json)
        if len(self.calls) == 1:
            assert body["tool_choice"]["function"]["name"] == "validate_day"
            assert "observation" in body["messages"][0]["content"]
            assert "Final JSON shape" not in body["messages"][0]["content"]
            message = {
                "tool_calls": [
                    {
                        "id": "offline-read",
                        "type": "function",
                        "function": {
                            "name": "validate_day",
                            "arguments": '{"selected_date":"2026-03-29"}',
                        },
                    }
                ]
            }
            finish = "tool_calls"
        else:
            assert not {"tools", "tool_choice", "parallel_tool_calls"} & body.keys()
            schema = body["response_format"]["json_schema"]
            assert schema["strict"] and set(schema["schema"]["properties"]) == {
                "observation_ids"
            }
            if self.quota and len(self.calls) == 2:
                return HttpReply(status=429, retry_after="1")
            ids = schema["schema"]["properties"]["observation_ids"]["items"]["enum"]
            message = {
                "content": json.dumps({"observation_ids": ids[:3], **self.extras}),
                "reasoning": "PRIVATE_REASONING_SENTINEL",
            }
            finish = "stop"
        return HttpReply(
            status=200,
            body=json.dumps(
                {
                    "choices": [{"finish_reason": finish, "message": message}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 5},
                    "untrusted_metadata": "PRIVATE_METADATA_SENTINEL",
                }
            ).encode(),
        )


def prepared(model: Model, clock: Clock, *, cap: int = 4) -> PreparedReview:
    snapshot = context_snapshot()
    tools = FrozenTools(snapshot)
    run = ProviderRun(
        settings=ProviderSettings(
            enabled=True,
            groq_free_account_confirmed=True,
            groq_api_key=SecretStr("offline-key"),
            max_http_calls=cap,
        ),
        transport=model,
        snapshot_id=str(snapshot.id),
        snapshot_json=tools.provider_context(),
        task="Select useful issued observations",
        tools=tuple(
            ToolContract(name=name, description="Frozen tool", parameters_json=schema)
            for name, schema in tools.contracts()
        ),
        check_context=lambda: None,
        admit=lambda: True,
        monotonic=clock,
        waiter=clock.wait,
        force_validate_day=True,
        observation_selection=True,
    )
    return PreparedReview(
        cast(RunContext, SimpleNamespace(snapshot=snapshot)),
        tools,
        run,
        observation_selection=True,
    )


def test_genuine_contract_fake_transport_two_calls_and_server_text_only() -> None:
    model, clock = Model(), Clock()
    p = prepared(model, clock)
    p.execute_tool(p.run.call())
    rendered = p.finish_selection(p.run.call())
    assert p.run.http_calls == 2 and p.run.tool_calls == 1
    assert rendered.answer.explanation == "".join(
        x.text for x in rendered.presentation.segments
    )
    assert "PRIVATE_" not in rendered.model_dump_json()
    assert "observation_ids" not in rendered.model_dump_json()
    p.tools.validate_references(rendered.answer.model_dump_json())


def test_selection_retry_reuses_exact_catalog_request_and_run() -> None:
    model, clock = Model(quota=True), Clock()
    p = prepared(model, clock)
    run_id = p.run.run_id
    p.execute_tool(p.run.call())
    rendered = p.finish_selection(p.run.call())
    assert rendered.presentation.status == "ready"
    assert p.run.run_id == run_id and p.run.http_calls == 3 and p.run.tool_calls == 1
    assert p.run.quota_retries == 1 and p.run.switches == 0
    assert model.calls[1].body_json == model.calls[2].body_json
    assert p.run.metadata().usage_complete is False


@pytest.mark.parametrize(
    "field",
    [
        "explanation",
        "reason",
        "title",
        "action_text",
        "URL",
        "scope",
        "references",
        "selected_date",
    ],
)
def test_free_text_identity_or_url_fields_cannot_bypass_selection(
    field: str, caplog: pytest.LogCaptureFixture
) -> None:
    model, clock = Model(extras={field: "PRIVATE_UNSUPPORTED_CLAIM_SENTINEL"}), Clock()
    p = prepared(model, clock)
    p.execute_tool(p.run.call())
    with pytest.raises(AgentFailure, match="^invalid_evidence$"):
        p.finish_selection(p.run.call())
    assert p.run.http_calls == 2 and p.run.tool_calls == 1
    assert "PRIVATE_" not in caplog.text


@pytest.mark.parametrize("event", ["cancel", "deadline", "cap", "cancel_during_retry"])
def test_selection_lifecycle_never_dispatches_after_boundary(event: str) -> None:
    model, clock = Model(quota=event == "cancel_during_retry"), Clock()
    p = prepared(model, clock, cap=1 if event == "cap" else 4)
    p.execute_tool(p.run.call())
    if event == "cancel":
        p.run.cancel()
    if event == "deadline":
        clock.now = 45
    if event == "cancel_during_retry":
        clock.after_wait = p.run.cancel
    with pytest.raises(AgentFailure):
        p.run.call()
    assert len(model.calls) == (2 if event == "cancel_during_retry" else 1)
    assert p.run.quota_retries == 0
