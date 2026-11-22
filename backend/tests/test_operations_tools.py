"""Detached tools/evidence and offline fixtures; no database/provider required."""

import json
from datetime import date
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from app.operations.checks import evaluate
from app.operations.evals import (
    EvalFixture,
    fixture_snapshot,
    load_fixtures,
    run_evaluations,
)
from app.operations.schemas import (
    Activity,
    Actual,
    Eligibility,
    Entity,
    OperationError,
    SavedSlot,
    SavedTeam,
    Snapshot,
)
from app.operations.tools import READ_TOOLS, VALIDATION_RESULT_BYTES, FrozenTools

FIXTURES = load_fixtures()


def snapshot(name: str = "planned_actual_limits_are_independent") -> Snapshot:
    return fixture_snapshot(next(item for item in FIXTURES if item.name == name))


def arguments(**kwargs: object) -> str:
    return json.dumps({"selected_date": "2026-03-29", **kwargs})


def context_snapshot(
    *,
    selected_archived: bool = False,
    activity_count: int = 1,
    pool_size: int = 4,
    dog_count: int = 14,
    with_team: bool = False,
    with_actual: bool = False,
    missing_eligibility: bool = False,
) -> Snapshot:
    """Four working participants and ten unrelated archived dogs, detached only."""
    base = snapshot("planned_is_not_completed")
    dogs = tuple(
        base.dogs[0].model_copy(
            update={
                "id": UUID(int=index + 1),
                "name": f"Excluded free-text name {index}",
                "lifecycle": "active" if index < pool_size else "archived",
                "dog_class": "standard" if index < pool_size else None,
                "availability": "available" if index < pool_size else None,
                "housing_code": "A1-01" if index < pool_size else None,
                "housing_source": "canonical" if index < pool_size else "unhoused",
            }
        )
        for index in range(dog_count)
    )
    participants = tuple(dog.id for dog in dogs[:pool_size])
    if selected_archived:
        participants = (*participants[:-1], dogs[-1].id)
    eligibility = tuple(
        Eligibility(
            dog_id=dog_id,
            reasons=("archived",)
            if selected_archived and dog_id == dogs[-1].id
            else (),
        )
        for dog_id in participants
    )
    teams = (
        (
            SavedTeam(
                sequence=1,
                size=4,
                slots=tuple(
                    SavedSlot(
                        dog_id=dog_id,
                        pair_index=index // 2,
                        side="left" if index % 2 == 0 else "right",
                        role="lead" if index < 2 else "wheel",
                        order=index,
                    )
                    for index, dog_id in enumerate(participants[:4])
                ),
            ),
        )
        if with_team
        else ()
    )
    activities = tuple(
        Activity(
            id=UUID(int=100 + index),
            sequence=index + 1,
            kind="training",
            distance_km=5,
            participants=participants,
            eligibility=() if missing_eligibility else eligibility,
            teams=teams,
            actual_status="matches_plan" if with_actual else "not_recorded",
        )
        for index in range(activity_count)
    )
    actual = (
        (Actual(id=UUID(int=200), distance_km=10, participants=participants),)
        if with_actual
        else ()
    )
    checks, evidence = evaluate(
        base.selected_date,
        day=Entity(kind="day", id=str(base.selected_date)),
        activities=activities,
        dogs=dogs,
        actual=actual,
        locations=(),
        plan_exists=bool(activities),
    )
    return base.model_copy(
        update={
            "activities": activities,
            "dogs": dogs,
            "actual": actual,
            "locations": (),
            "plan_exists": bool(activities),
            "checks": checks,
            "evidence": evidence,
        }
    )


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


def test_known_day_entity_cannot_be_attached_to_activity_evidence() -> None:
    state = snapshot()
    tools = FrozenTools(state)
    day = state.evidence[0].entities[0]
    assert day.kind == "day" and day.id == str(state.selected_date)
    issued = next(
        row
        for row in state.evidence
        if any(entity.kind == "activity" for entity in row.entities)
    )
    activity = next(entity for entity in issued.entities if entity.kind == "activity")
    assert day not in issued.entities
    payload = reference_payload(state)
    references = payload["references"]
    assert isinstance(references, list)
    references[0]["evidence_id"] = issued.id
    # Snapshot/date/evidence and the day identity are all genuinely issued, but
    # this pairing is invalid because the chosen evidence belongs to an activity.
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        tools.validate_references(json.dumps(payload))
    references[0]["entity"] = activity.model_dump(mode="json")
    assert (
        tools.validate_references(json.dumps(payload)).references[0].entity == activity
    )


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


def test_required_validation_retains_four_dog_pool_without_saved_teams_or_actual() -> (
    None
):
    state = context_snapshot()
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    plan = report["plan"]
    assert plan["exists"] is True and plan["activity_count"] == 1
    assert plan["selected_unique_dogs"] == plan["selected_participations"] == 4
    assert plan["omitted_activity_count"] == 0
    activity = plan["activities"][0]
    assert activity["id"] == str(state.activities[0].id)
    assert activity["kind"] == "training" and activity["distance_km"] == 5
    assert activity["selected_pool"] == [str(dog.id) for dog in state.dogs[:4]]
    assert activity["selected_pool_count"] == activity["eligible_count"] == 4
    assert activity["ineligible_count"] == activity["eligibility_unverified_count"] == 0
    assert activity["saved_teams"] == 0 and activity["actual_status"] == "not_recorded"
    assert report["actual"]["sessions"] == report["actual"]["dog_starts"] == 0
    assert report["actual"]["dog_km"] == report["actual"]["unique_dogs"] == 0
    assert report["omitted_selected_dog_state_count"] == 0
    assert len(report["selected_dog_states"]) == 4
    assert all(dog["lifecycle"] == "active" for dog in report["selected_dog_states"])
    assert report["finding_counts_by_scope"]["other_snapshot_dogs"] == 10
    assert report["status_counts"]["unverified"] == 10
    assert report["omitted_detail_count"] == 10
    assert {check["rule"] for check in report["checks"]} == {
        "SAVED_LINEUP",
        "ACTUAL_RECORDING",
    }
    assert len(state.checks) == sum(report["status_counts"].values())
    assert (
        len(
            FrozenTools(state)
            .execute("validate_day", arguments())
            .model_dump_json()
            .encode()
        )
        < 8192
    )
    # Canonical state/evidence remains available when an explicit read is useful.
    archived = state.dogs[-1]
    detail = json.loads(
        FrozenTools(state)
        .execute("get_dog_states", arguments(dog_ids=[str(archived.id)]))
        .data_json
    )
    assert detail[0]["id"] == str(archived.id)
    assert detail[0]["lifecycle"] == "archived"
    assert str(archived.id) not in json.dumps(report["evidence"])
    for check in report["checks"]:
        if check["rule"] == "DOG_STATE":
            assert check["scope"] == "other_snapshot_dogs"
            assert all(
                entity["id"] not in activity["selected_pool"]
                for entity in check["entities"]
            )
    assert "selected pool" not in report["actual"]


def test_archived_selected_dog_remains_explicitly_ineligible_not_unrelated() -> None:
    state = context_snapshot(selected_archived=True)
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    activity = report["plan"]["activities"][0]
    archived_id = str(state.dogs[-1].id)
    assert activity["eligible_count"] == 3 and activity["ineligible_count"] == 1
    assert activity["ineligible_participants"] == [
        {"dog_id": archived_id, "reasons": ["archived"]}
    ]
    selected = next(
        dog for dog in report["selected_dog_states"] if dog["id"] == archived_id
    )
    assert selected["lifecycle"] == "archived" and selected["class"] is None
    for rule in ["PARTICIPANT_ELIGIBILITY", "DOG_STATE"]:
        found = next(
            check
            for check in report["checks"]
            if check["rule"] == rule
            and any(entity["id"] == archived_id for entity in check["entities"])
        )
        assert found["scope"] == "plan_participants"


@pytest.mark.parametrize(
    ("activity_count", "pool_size", "with_team", "with_actual"),
    [
        (0, 0, False, False),
        (1, 0, False, False),
        (1, 4, False, False),
        (1, 4, True, False),
        (0, 4, False, True),
        (1, 4, False, True),
    ],
)
def test_plan_pool_teams_and_actual_are_independent(
    activity_count: int,
    pool_size: int,
    with_team: bool,
    with_actual: bool,
) -> None:
    state = context_snapshot(
        activity_count=activity_count,
        pool_size=pool_size,
        with_team=with_team,
        with_actual=with_actual,
    )
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    assert report["plan"]["exists"] is bool(activity_count)
    assert report["plan"]["selected_unique_dogs"] == (
        pool_size if activity_count else 0
    )
    assert report["plan"]["selected_participations"] == pool_size * activity_count
    assert report["actual"]["sessions"] == int(with_actual)
    assert report["actual"]["dog_starts"] == (pool_size if with_actual else 0)
    assert report["actual"]["dog_km"] == (pool_size * 10 if with_actual else 0)
    if activity_count:
        activity = report["plan"]["activities"][0]
        assert activity["selected_pool_count"] == pool_size
        assert activity["saved_teams"] == int(with_team)


def test_multiple_activities_count_unique_dogs_and_participations_separately() -> None:
    state = context_snapshot(activity_count=2)
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    assert report["plan"]["activity_count"] == 2
    assert report["plan"]["selected_unique_dogs"] == 4
    assert report["plan"]["selected_participations"] == 8
    assert [row["selected_pool_count"] for row in report["plan"]["activities"]] == [
        4,
        4,
    ]


def test_missing_eligibility_detail_is_unknown_not_success_or_zero_pool() -> None:
    state = context_snapshot(missing_eligibility=True)
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    activity = report["plan"]["activities"][0]
    assert activity["selected_pool_count"] == 4
    assert activity["eligible_count"] == activity["ineligible_count"] == 0
    assert activity["eligibility_unverified_count"] == 4


@pytest.mark.parametrize(
    "activity_count,pool_size,dog_count", [(1, 4, 14), (32, 60, 60)]
)
def test_validation_evidence_is_frozen_scoped_bounded_and_omissions_are_truthful(
    activity_count: int,
    pool_size: int,
    dog_count: int,
) -> None:
    state = context_snapshot(
        activity_count=activity_count, pool_size=pool_size, dog_count=dog_count
    )
    before = state.model_dump_json()
    tools = FrozenTools(state)
    output = tools.execute("validate_day", arguments())
    report = json.loads(output.data_json)
    assert output == tools.execute("validate_day", arguments())
    assert state.model_dump_json() == before
    assert len(output.model_dump_json().encode()) <= VALIDATION_RESULT_BYTES
    assert report["plan"]["omitted_activity_count"] == activity_count - len(
        report["plan"]["activities"]
    )
    assert report["omitted_selected_dog_state_count"] == pool_size - len(
        report["selected_dog_states"]
    )
    important = [row for row in state.checks if row.status != "pass"]
    assert report["omitted_detail_count"] == len(important) - len(report["checks"])
    assert sum(report["status_counts"].values()) == len(state.checks)
    assert sum(report["finding_counts_by_scope"].values()) == len(important)
    assert len(report["checks"]) <= 32
    evidence = {row.id: row.model_dump(mode="json") for row in state.evidence}
    emitted = {row["id"]: row for row in report["evidence"]}
    assert set(output.evidence_ids) == set(emitted)
    assert all(evidence[key] == row for key, row in emitted.items())
    for row in report["plan"]["activities"]:
        for evidence_id in row["evidence_ids"]:
            assert {"kind": "activity", "id": row["id"]} in emitted[evidence_id][
                "entities"
            ]
    for row in report["selected_dog_states"]:
        for evidence_id in row["evidence_ids"]:
            assert {"kind": "dog", "id": row["id"]} in emitted[evidence_id]["entities"]
    for check in report["checks"]:
        for evidence_id in check["evidence_ids"]:
            assert emitted[evidence_id]["entities"] == check["entities"]
    for section in [report["plan"], report["actual"]]:
        for evidence_id in section["evidence_ids"]:
            assert emitted[evidence_id]["entities"] == [
                {"kind": "day", "id": str(state.selected_date)}
            ]
    assert "Excluded free-text name" not in output.data_json
    assert not {"notes", "title", "history", "dogs", "locations"} & set(report)


def test_archived_actual_participant_state_is_not_compacted_as_unrelated() -> None:
    state = context_snapshot(selected_archived=True, activity_count=0, with_actual=True)
    before = state.model_dump_json()
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    archived_id = str(state.dogs[-1].id)
    actual_state = next(
        row
        for row in report["checks"]
        if row["rule"] == "DOG_STATE"
        and row["entities"] == [{"kind": "dog", "id": archived_id}]
    )
    assert actual_state["status"] == "unverified"
    assert actual_state["scope"] == "actual"
    assert report["finding_counts_by_scope"]["actual"] == 1
    assert report["finding_counts_by_scope"]["other_snapshot_dogs"] == 9
    assert report["omitted_detail_count"] == 9
    assert report["actual"] == {
        "sessions": 1,
        "dog_starts": 4,
        "dog_km": 40,
        "unique_dogs": 4,
        "evidence_ids": [state.evidence[-1].id],
    }
    assert report["plan"]["selected_unique_dogs"] == 0
    assert state.model_dump_json() == before


def test_actual_violations_and_unrelated_missing_active_state_remain_visible() -> None:
    base = context_snapshot(activity_count=0, with_actual=True)
    # Four real starts on the date exceed the existing per-dog30km rule.
    actual = tuple(
        base.actual[0].model_copy(update={"id": UUID(int=200 + index)})
        for index in range(4)
    )
    missing = base.dogs[-1].model_copy(update={"lifecycle": "active"})
    dogs = (*base.dogs[:-1], missing)
    checks, evidence = evaluate(
        base.selected_date,
        day=Entity(kind="day", id=str(base.selected_date)),
        activities=(),
        dogs=dogs,
        actual=actual,
        locations=(),
        plan_exists=False,
    )
    state = base.model_copy(
        update={
            "dogs": dogs,
            "actual": actual,
            "checks": checks,
            "evidence": evidence,
        }
    )
    report = json.loads(
        FrozenTools(state).execute("validate_day", arguments()).data_json
    )
    violations = [row for row in report["checks"] if row["status"] == "violation"]
    assert len(violations) == 4
    assert all(
        row["rule"] == "ACTUAL_DAILY_KM" and row["scope"] == "actual"
        for row in violations
    )
    missing_checks = [
        row
        for row in report["checks"]
        if row["entities"] == [{"kind": "dog", "id": str(missing.id)}]
    ]
    assert {row["rule"] for row in missing_checks} == {
        "DOG_STATE",
        "DATED_STATE_MISSING",
    }
    assert all(row["scope"] == "other_snapshot_dogs" for row in missing_checks)
    assert report["actual"]["sessions"] == 4
    assert report["actual"]["dog_starts"] == 16
    assert report["actual"]["dog_km"] == 160
    assert report["omitted_detail_count"] == 9
    emitted = {row["id"] for row in report["evidence"]}
    assert all(set(row["evidence_ids"]) <= emitted for row in report["checks"])
