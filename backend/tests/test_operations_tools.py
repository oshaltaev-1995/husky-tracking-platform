"""Detached tools/evidence and offline fixtures; no database/provider required."""

import json
from datetime import date
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from app.operations.evals import (
    EvalFixture,
    fixture_snapshot,
    load_fixtures,
    run_evaluations,
)
from app.operations.schemas import Entity, OperationError, Snapshot
from app.operations.tools import READ_TOOLS, FrozenTools

FIXTURES = load_fixtures()


def snapshot(name: str = "planned_actual_limits_are_independent") -> Snapshot:
    return fixture_snapshot(next(item for item in FIXTURES if item.name == name))


def arguments(**kwargs: object) -> str:
    return json.dumps({"selected_date": "2026-03-29", **kwargs})


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda item: item.name)
def test_offline_rules_have_matching_dated_evidence(fixture: EvalFixture) -> None:
    results = {item.scenario: item for item in run_evaluations()}
    name = fixture.name
    result = results[name]
    assert result.status == "PASS"
    assert len(result.expected_rules) == len(result.matched_evidence_ids)
    state = snapshot(name)
    lookup = {item.id: item for item in state.evidence}
    for check in state.checks:
        assert check.selected_date == date(2026, 3, 29)
        assert check.evidence_ids
        for evidence_id in check.evidence_ids:
            found = lookup[evidence_id]
            assert found.selected_date == check.selected_date
            assert found.entities == check.entities
            assert found.values


def test_snapshot_is_deeply_immutable_and_detached() -> None:
    state = snapshot()

    def visit(value: object) -> None:
        assert not isinstance(value, (dict, list, set))
        if isinstance(value, BaseModel):
            assert value.model_config.get("frozen") is True
            for key in type(value).model_fields:
                visit(getattr(value, key))
        elif isinstance(value, tuple):
            for item in value:
                visit(item)

    visit(state)
    with pytest.raises(ValidationError):
        state.dogs[0].name = "Changed"
    with pytest.raises(ValidationError):
        state.activities[0].distance_km = 3
    with pytest.raises(ValidationError):
        state.selected_date = date(2026, 3, 31)


@pytest.mark.parametrize("tool", READ_TOOLS)
def test_every_tool_reads_same_selected_date_and_snapshot(tool: str) -> None:
    state = snapshot()
    tools = FrozenTools(state)
    args = arguments(
        **(
            {"dog_ids": [str(state.dogs[0].id)]}
            if tool in {"get_dog_states", "get_workload"}
            else {}
        )
    )
    before = state.model_dump_json()
    first = tools.execute(tool, args)
    assert first.snapshot_id == state.id
    assert first.selected_date == state.selected_date
    assert first == tools.execute(tool, args)
    json.loads(first.data_json)
    assert state.model_dump_json() == before


def test_workload_before_date_and_actual_day_are_explicitly_separate() -> None:
    state = snapshot()
    result = json.loads(
        FrozenTools(state)
        .execute("get_workload", arguments(dog_ids=[str(state.dogs[0].id)]))
        .data_json
    )
    assert result["planning_actual_cutoff"] == "strictly_before_selected_date"
    assert result["actual_on_selected_date_is_separate"] is True
    dog = result["dogs"][0]
    assert dog["km_14d_before"] == 20
    assert dog["season_km_before"] == 100
    assert dog["actual_km_on_date"] == 30
    assert dog["starts_on_date"] == 3
    assert "name" not in dog


def test_selected_pool_is_retained_when_no_saved_teams_exist() -> None:
    state = snapshot("planned_is_not_completed")
    tools = FrozenTools(state)
    result = json.loads(tools.execute("get_saved_teams", arguments()).data_json)
    assert result[0]["selected_pool"] == [str(state.dogs[0].id)]
    assert result[0]["saved_teams"] == []
    report = json.loads(tools.execute("validate_day", arguments()).data_json)
    assert {"rule": "SAVED_LINEUP", "status": "attention"}.items() <= next(
        item.items() for item in report["checks"] if item["rule"] == "SAVED_LINEUP"
    )
    assert "not a guarantee of training safety" in report["qualification"]


def test_untrusted_name_is_data_and_does_not_change_registry_or_provider_context() -> (
    None
):
    state = snapshot("dense_housing_untrusted_name")
    tools = FrozenTools(state)
    contracts_before = tools.contracts()
    result = tools.execute("get_dog_states", arguments(dog_ids=[str(state.dogs[0].id)]))
    assert "execute_sql" in json.loads(result.data_json)[0]["name"]
    assert tools.contracts() == contracts_before
    assert len(contracts_before) == 6
    assert "execute_sql" not in tools.provider_context()
    assert "switch provider" not in tools.provider_context()
    with pytest.raises(OperationError, match="^tool_not_allowed$"):
        tools.execute("execute_sql", arguments())
    for name, schema_json in contracts_before:
        schema = json.loads(schema_json)
        assert schema["additionalProperties"] is False
        fields = {"selected_date"}
        if name in {"get_dog_states", "get_workload", "get_housing"}:
            fields.add("dog_ids")
        if name in {"get_day_plan", "get_saved_teams"}:
            fields.add("activity_ids")
        assert set(schema["properties"]) == fields
        required = {"selected_date"}
        if name in {"get_dog_states", "get_workload"}:
            required.add("dog_ids")
            assert schema["properties"]["dog_ids"]["minItems"] == 1
        assert set(schema["required"]) == required


@pytest.mark.parametrize(
    ("tool", "body", "error"),
    [
        ("http", arguments(), "tool_not_allowed"),
        ("shell", arguments(), "tool_not_allowed"),
        ("get_day_plan", "not JSON", "invalid_tool_arguments"),
        ("get_day_plan", "{" + "x" * 8193, "invalid_tool_arguments"),
        ("get_day_plan", arguments(workspace_id="other"), "invalid_tool_arguments"),
        ("get_day_plan", arguments(sql="SELECT 1"), "invalid_tool_arguments"),
        (
            "get_day_plan",
            arguments(url="https://example.com"),
            "invalid_tool_arguments",
        ),
        ("get_day_plan", arguments(provider="paid"), "invalid_tool_arguments"),
        ("get_day_plan", arguments(selected_date="2026-03-31"), "date_not_in_snapshot"),
        (
            "get_day_plan",
            arguments(selected_date="2026-3-29"),
            "invalid_tool_arguments",
        ),
        ("get_day_plan", arguments(selected_date=20260329), "invalid_tool_arguments"),
        ("get_dog_states", arguments(), "dog_selection_required"),
        ("get_workload", arguments(), "dog_selection_required"),
        ("get_dog_states", arguments(dog_ids=[5]), "invalid_tool_arguments"),
        (
            "get_dog_states",
            arguments(dog_ids=[str(UUID(int=55))]),
            "entity_not_in_snapshot",
        ),
        (
            "get_day_plan",
            arguments(activity_ids=[str(UUID(int=55))]),
            "entity_not_in_snapshot",
        ),
        (
            "get_dog_states",
            arguments(dog_ids=[str(UUID(int=1)), str(UUID(int=1))]),
            "invalid_tool_arguments",
        ),
        (
            "get_day_plan",
            arguments(activity_ids=[str(UUID(int=100)), str(UUID(int=100))]),
            "invalid_tool_arguments",
        ),
        (
            "get_dog_states",
            arguments(activity_ids=[str(UUID(int=100))]),
            "invalid_tool_arguments",
        ),
        (
            "get_day_plan",
            arguments(dog_ids=[str(UUID(int=1))]),
            "invalid_tool_arguments",
        ),
        (
            "get_dog_states",
            arguments(dog_ids=[str(UUID(int=1))] * 61),
            "invalid_tool_arguments",
        ),
    ],
)
def test_registry_rejects_unscoped_or_unsupported_arguments(
    tool: str, body: str, error: str
) -> None:
    state = snapshot()
    before = state.model_dump_json()
    with pytest.raises(OperationError) as raised:
        FrozenTools(state).execute(tool, body)
    assert raised.value.code == error
    assert str(raised.value) == error
    assert state.model_dump_json() == before


def reference_payload(state: Snapshot) -> dict[str, object]:
    found = state.evidence[0]
    return {
        "explanation": "Free text is not automatically truth-certified.",
        "references": [
            {
                "snapshot_id": str(state.id),
                "selected_date": state.selected_date.isoformat(),
                "evidence_id": found.id,
                "entity": found.entities[0].model_dump(mode="json"),
            }
        ],
    }


def test_valid_reference_is_server_owned_and_link_is_built_locally() -> None:
    state = snapshot()
    tools = FrozenTools(state)
    answer = tools.validate_references(json.dumps(reference_payload(state)))
    assert answer.references[0].evidence_id == state.evidence[0].id
    assert tools.link(answer.references[0].entity) == "/demo/daily?date=2026-03-29"
    assert tools.link(Entity(kind="dog", id=str(state.dogs[0].id))) == (
        f"/demo/dogs/{state.dogs[0].id}?tab=work"
    )
    assert tools.link(Entity(kind="activity", id=str(state.activities[0].id))) == (
        f"/demo/daily/2026-03-29/activities/{state.activities[0].id}/teams"
    )
    assert tools.link(Entity(kind="location", id=state.locations[0].code)) == (
        "/demo/kennel?date=2026-03-29"
    )
    assert tools.link(Entity(kind="actual", id=str(state.actual[0].id))) == (
        "/demo/daily-entry?date=2026-03-29"
    )
    with pytest.raises(OperationError, match="^entity_not_in_snapshot$"):
        tools.link(Entity(kind="dog", id="https://untrusted.example"))


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("snapshot_id", str(UUID(int=1000))),
        ("selected_date", "2026-03-31"),
        ("evidence_id", "made-up-evidence"),
        ("entity", {"kind": "dog", "id": str(UUID(int=1))}),
        ("url", "https://untrusted.example"),
    ],
)
def test_references_reject_cross_snapshot_date_entity_and_invented_evidence(
    field: str, wrong: object
) -> None:
    state = snapshot()
    payload = reference_payload(state)
    references = payload["references"]
    assert isinstance(references, list)
    references[0][field] = wrong
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        FrozenTools(state).validate_references(json.dumps(payload))


def test_tool_outputs_have_no_mutable_alias_back_into_frozen_snapshot() -> None:
    state = snapshot()
    tools = FrozenTools(state)
    first = tools.execute("get_day_plan", arguments())
    decoded = json.loads(first.data_json)
    decoded["activities"][0]["participants"].clear()
    assert tools.execute("get_day_plan", arguments()) == first
    assert state.activities[0].participants


@pytest.mark.parametrize(
    "raw",
    [
        '{"selected_date":"2026-03-31","selected_date":"2026-03-29"}',
        '{"selected_date":"2026-03-29","dog_ids":NaN}',
    ],
)
def test_duplicate_json_keys_and_nonfinite_arguments_are_rejected(raw: str) -> None:
    with pytest.raises(OperationError, match="invalid_tool_arguments"):
        FrozenTools(snapshot()).execute("get_day_plan", raw)


def test_housing_selection_keeps_occupancy_without_other_dog_identities() -> None:
    state = snapshot("dense_housing_untrusted_name")
    selected = str(state.dogs[0].id)
    output = json.loads(
        FrozenTools(state)
        .execute(
            "get_housing",
            arguments(dog_ids=[selected]),
        )
        .data_json
    )
    assert len(output["dogs"]) == 1
    location = output["locations"][0]
    assert location["occupancy"] == 4
    assert location["selected_residents"] == [selected]
    assert "residents" not in location


@pytest.mark.parametrize(
    "enabled,admitted,code",
    [
        (False, True, "agent_disabled"),
        (True, False, "app_rate_limited"),
    ],
)
def test_preparation_disabled_or_denied_has_no_snapshot_or_transport(
    enabled: bool,
    admitted: bool,
    code: str,
) -> None:
    from unittest.mock import Mock

    from pydantic import SecretStr

    from app.operations.foundation import prepare_review
    from app.operations.provider_models import AgentFailure, ProviderSettings

    reader, transport = Mock(), Mock()
    with pytest.raises(AgentFailure) as failure:
        prepare_review(
            reader=reader,
            selected_date=date(2026, 3, 29),
            current_cookie=lambda: "not-used",
            cancelled=lambda: False,
            settings=ProviderSettings(
                enabled=enabled, groq_api_key=SecretStr("fake-key")
            ),
            transport=transport,
            admit=lambda: admitted,
        )
    assert failure.value.code == code
    reader.capture.assert_not_called()
    transport.assert_not_called()


@pytest.mark.parametrize("name", READ_TOOLS)
def test_minimal_published_schema_request_executes_on_its_snapshot(name: str) -> None:
    state = snapshot()
    tools = FrozenTools(state)
    schema = json.loads(dict(tools.contracts())[name])
    request: dict[str, object] = {"selected_date": str(state.selected_date)}
    if "dog_ids" in schema["required"]:
        request["dog_ids"] = [str(state.dogs[0].id)]
    assert set(request) == set(schema["required"])
    result = tools.execute(name, json.dumps(request))
    assert result.tool == name and result.snapshot_id == state.id


@pytest.mark.parametrize("name", ["get_day_plan", "get_saved_teams", "validate_day"])
def test_unsupported_empty_selector_is_not_silently_accepted(name: str) -> None:
    with pytest.raises(OperationError, match="invalid_tool_arguments"):
        FrozenTools(snapshot()).execute(name, arguments(dog_ids=[]))
