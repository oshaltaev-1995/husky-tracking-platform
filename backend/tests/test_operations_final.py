"""Final-only protocol/facts regressions: deterministic fake transport, no DB/keys."""

from __future__ import annotations

import json
from collections.abc import Callable
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import SecretStr
from test_operations_rate_recovery import (
    Clock,
    Transport,
    active,
    final,
    tool,
    validate_once,
)
from test_operations_tools import context_snapshot

from app.operations.final_request import FINAL_INSTRUCTIONS, build_final_request
from app.operations.foundation import prepare_review
from app.operations.provider_models import (
    AgentFailure,
    HttpReply,
    HttpRequest,
    ProviderSettings,
    ToolContract,
)
from app.operations.review import OperationsReviewService
from app.operations.schemas import Snapshot
from app.operations.snapshot import RunContext, SnapshotReader
from app.operations.tools import FrozenTools


def config(**changes: Any) -> ProviderSettings:
    return ProviderSettings(
        enabled=True,
        groq_free_account_confirmed=True,
        groq_api_key=SecretStr("offline-fixture-key"),
        max_http_calls=4,
        **changes,
    )


def contracts(tools: FrozenTools) -> tuple[ToolContract, ...]:
    return tuple(
        ToolContract(name=name, description="Frozen read", parameters_json=schema)
        for name, schema in tools.contracts()
    )


def parse_data_message(message: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(message["content"].split("\n", 1)[1]))


class Reader:
    """Capture once; freshness checks carry no fact reads or Session to transport."""

    def __init__(self, state: Snapshot) -> None:
        self.state = state
        self.captures = 0
        self.invalidated = False

    def capture(self, *_: object, **__: object) -> RunContext:
        self.captures += 1
        assert self.captures == 1
        return cast(RunContext, SimpleNamespace(snapshot=self.state))

    def check(self, *_: object, **__: object) -> None:
        if self.invalidated:
            raise AgentFailure("context_changed", http_status=409)


class Model:
    def __init__(self, state: Snapshot) -> None:
        self.state = state
        self.calls: list[HttpRequest] = []
        self.final_mutation: Callable[[dict[str, Any]], None] = lambda _: None
        self.tool_result: dict[str, Any] | None = None
        self.final_data: dict[str, Any] | None = None

    def __call__(self, request: HttpRequest) -> HttpReply:
        self.calls.append(request)
        body = json.loads(request.body_json)
        if len(self.calls) == 1:
            assert body["tool_choice"] == {
                "type": "function",
                "function": {"name": "validate_day"},
            }
            assert "response_format" not in body
            arguments = json.dumps({"selected_date": str(self.state.selected_date)})
            reply = json.loads(tool().body)
            reply["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = (
                arguments
            )
            return HttpReply(status=200, body=json.dumps(reply).encode())
        assert len(self.calls) == 2, "No repair/new review is allowed"
        assert not {"tools", "tool_choice", "parallel_tool_calls"} & body.keys()
        assert body["stream"] is False
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["max_completion_tokens"] == 1024
        assert body["reasoning_effort"] == "low" and body["include_reasoning"] is False
        assert [m["role"] for m in body["messages"]] == [
            "system",
            "user",
            "user",
            "user",
            "user",
        ]
        first = json.loads(self.calls[0].body_json)
        assert body["messages"][1:3] == first["messages"][1:3]
        self.tool_result = parse_data_message(body["messages"][3])
        expected = FrozenTools(self.state).execute(
            "validate_day", json.dumps({"selected_date": str(self.state.selected_date)})
        )
        assert self.tool_result == json.loads(expected.model_dump_json())
        assert (
            body["messages"][3]["content"].split("\n", 1)[1]
            == expected.model_dump_json()
        )
        self.final_data = json.loads(self.tool_result["data_json"])
        catalog = parse_data_message(body["messages"][4])
        assert catalog["snapshot_id"] == self.tool_result["snapshot_id"]
        assert catalog["selected_date"] == self.tool_result["selected_date"]
        assert (
            body["response_format"]["json_schema"]["name"]
            == "operations_observation_selection"
        )
        assert (
            "explanation"
            not in body["response_format"]["json_schema"]["schema"]["properties"]
        )
        content = {
            "observation_ids": [item["id"] for item in catalog["observations"][:3]]
        }
        self.final_mutation(content)
        return final(json.dumps(content))


@pytest.mark.parametrize("scenario", ["empty", "selected", "teams_actual", "omitted"])
def test_two_phase_full_service_accepts_real_frozen_references_and_preserves_facts(
    scenario: str,
) -> None:
    state = context_snapshot(
        activity_count=0 if scenario == "empty" else 32 if scenario == "omitted" else 1,
        pool_size=0 if scenario == "empty" else 4,
        with_team=scenario == "teams_actual",
        with_actual=scenario == "teams_actual",
        missing_eligibility=scenario == "omitted",
    )
    reader, model = Reader(state), Model(state)
    service = OperationsReviewService(
        cast(SnapshotReader, reader), config(), lambda _: model
    )
    result = service.review(
        "offline-cookie", state.selected_date, lambda: False, monotonic()
    )
    assert reader.captures == 1
    assert result.http_calls == 2 and result.tool_calls == 1 and not result.fallback
    assert result.presentation.status == "ready"
    assert result.explanation and model.final_data is not None
    data = model.final_data
    assert data["plan"]["selected_unique_dogs"] == (0 if scenario == "empty" else 4)
    assert data["actual"]["sessions"] == (1 if scenario == "teams_actual" else 0)
    if scenario == "selected":
        activity = data["plan"]["activities"][0]
        assert activity["selected_pool_count"] == 4
        assert (
            activity["saved_teams"] == 0 and activity["actual_status"] == "not_recorded"
        )
        assert len(data["selected_dog_states"]) == 4
        assert all(dog["lifecycle"] == "active" for dog in data["selected_dog_states"])
        assert data["finding_counts_by_scope"]["other_snapshot_dogs"] == 10
    elif scenario == "teams_actual":
        activity = data["plan"]["activities"][0]
        assert (
            activity["saved_teams"] == 1 and activity["actual_status"] == "matches_plan"
        )
        assert data["actual"]["dog_starts"] == 4 and data["actual"]["dog_km"] == 40
    elif scenario == "omitted":
        assert (
            data["plan"]["omitted_activity_count"] > 0
            or data["omitted_detail_count"] > 0
        )
        assert "unknown, not zero" in data["qualification"]
        assert data["plan"]["selected_participations"] == 128
    assert "other_snapshot_dogs" in FINAL_INSTRUCTIONS
    assert "missing or omitted information is NOT zero" in FINAL_INSTRUCTIONS


@pytest.mark.parametrize(
    "invalid", ["snapshot", "date", "evidence", "entity_id", "kind", "extra"]
)
def test_selection_final_rejects_model_owned_identity_and_extra_fields(
    invalid: str,
) -> None:
    state = context_snapshot()
    reader, model = Reader(state), Model(state)

    def mutate(content: dict[str, Any]) -> None:
        # The new final cannot supply or repair its own evidence/identity fields.
        content[invalid] = "untrusted-model-field"

    model.final_mutation = mutate
    service = OperationsReviewService(
        cast(SnapshotReader, reader), config(), lambda _: model
    )
    with pytest.raises(AgentFailure, match="^invalid_evidence$"):
        service.review(
            "offline-cookie", state.selected_date, lambda: False, monotonic()
        )
    assert len(model.calls) == 2 and reader.captures == 1


def test_final_schema_uses_supported_required_object_subset_and_same_limits() -> None:
    state = context_snapshot()
    tools = FrozenTools(state)
    output = tools.execute(
        "validate_day", json.dumps({"selected_date": str(state.selected_date)})
    )
    settings = config()
    request = build_final_request(
        settings,
        task="Review this day",
        snapshot_json=tools.provider_context(),
        tools=contracts(tools),
        validation_output_json=output.model_dump_json(),
        timeout_seconds=12,
    )
    body = json.loads(request.body_json)

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            assert (
                not {"minLength", "maxLength", "minItems", "maxItems", "format", "$ref"}
                & value.keys()
            )
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(body["response_format"]["json_schema"]["schema"])
    assert request.response_limit_bytes == settings.max_response_bytes
    assert request.retries == 0 and request.follow_redirects is False
    assert len(request.body_json.encode()) <= settings.max_input_bytes


def test_unexpected_final_tool_never_executes_or_gains_third_request() -> None:
    clock = Clock()
    transport = Transport(tool(), tool("get_day_plan"), final())
    run = active(transport, clock)
    validate_once(run)
    with pytest.raises(AgentFailure, match="^forbidden_tool$"):
        run.call()
    assert run.http_calls == 2 and run.tool_calls == 1


@pytest.mark.parametrize("when", ["before_final", "during_final"])
def test_reset_context_fences_final_without_new_snapshot_or_dispatch(when: str) -> None:
    state = context_snapshot()
    reader, model = Reader(state), Model(state)
    prepared = prepare_review(
        reader=cast(SnapshotReader, reader),
        selected_date=state.selected_date,
        current_cookie=lambda: "offline-cookie",
        cancelled=lambda: False,
        settings=config(),
        transport=model,
        admit=lambda: True,
        force_validate_day=True,
        observation_selection=True,
    )
    prepared.execute_tool(prepared.run.call())
    if when == "before_final":
        reader.invalidated = True
    else:
        model.final_mutation = lambda _: setattr(reader, "invalidated", True)
    with pytest.raises(AgentFailure, match="^context_changed$"):
        prepared.run.call()
    assert reader.captures == 1
    assert len(model.calls) == (1 if when == "before_final" else 2)


def test_missing_actual_evidence_stays_unknown_instead_of_zero() -> None:
    state = context_snapshot()
    removed_ids = {
        evidence_id
        for check in state.checks
        if check.rule == "ACTUAL_LEDGER"
        for evidence_id in check.evidence_ids
    }
    state = state.model_copy(
        update={
            "checks": tuple(
                check for check in state.checks if check.rule != "ACTUAL_LEDGER"
            ),
            "evidence": tuple(
                row for row in state.evidence if row.id not in removed_ids
            ),
        }
    )
    reader, model = Reader(state), Model(state)
    service = OperationsReviewService(
        cast(SnapshotReader, reader), config(), lambda _: model
    )
    result = service.review(
        "offline-cookie", state.selected_date, lambda: False, monotonic()
    )
    assert result.http_calls == 2 and model.final_data is not None
    assert model.final_data["actual"]["sessions"] is None
    assert model.final_data["actual"]["dog_starts"] is None
    assert model.final_data["actual"]["dog_km"] is None
    assert "0 recorded sessions" not in result.explanation
    assert (
        "not verified" in result.explanation or "not established" in result.explanation
    )


def test_invalid_mandatory_tool_arguments_never_unlock_final_phase() -> None:
    state = context_snapshot()
    reader = Reader(state)
    bad = json.loads(tool().body)
    bad["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps(
        {
            "selected_date": "2026-03-28",
        }
    )
    transport = Transport(HttpReply(status=200, body=json.dumps(bad).encode()), final())
    prepared = prepare_review(
        reader=cast(SnapshotReader, reader),
        selected_date=state.selected_date,
        current_cookie=lambda: "offline-cookie",
        cancelled=lambda: False,
        settings=config(),
        transport=transport,
        admit=lambda: True,
        force_validate_day=True,
    )
    with pytest.raises(AgentFailure, match="^invalid_provider_response$"):
        prepared.execute_tool(prepared.run.call())
    assert prepared.run.tool_calls == 0
    assert not prepared.run.validated_current_attempt
    assert len(transport.requests) == 1
    with pytest.raises(AgentFailure, match="^run_finished$"):
        prepared.run.call()
    assert len(transport.requests) == 1


def test_premature_final_cannot_bypass_mandatory_validate_day() -> None:
    clock = Clock()
    transport = Transport(final(), tool())
    run = active(transport, clock)
    with pytest.raises(AgentFailure, match="^invalid_provider_response$"):
        run.call()
    assert len(transport.requests) == 1 and run.tool_calls == 0
    assert not run.validated_current_attempt
