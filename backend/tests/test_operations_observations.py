"""Finite application observations; detached data/fake selections, no DB/provider."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from test_operations_tools import context_snapshot

from app.operations.checks import evaluate
from app.operations.observations import (
    MAX_CATALOG_BYTES,
    MAX_OBSERVATIONS,
    ObservationCatalog,
)
from app.operations.schemas import Entity, OperationError, Snapshot, ToolResult
from app.operations.tools import FrozenTools


def tool_result(state: Snapshot) -> ToolResult:
    return FrozenTools(state).execute(
        "validate_day", json.dumps({"selected_date": str(state.selected_date)})
    )


def catalog(
    state: Snapshot | None = None, *, run: str = "one-frozen-run"
) -> ObservationCatalog:
    state = state or context_snapshot()
    return ObservationCatalog(state, tool_result(state), run, FrozenTools(state).link)


def rows(value: ObservationCatalog) -> list[dict[str, Any]]:
    return json.loads(value.provider_json())["observations"]


def select(value: ObservationCatalog, *kinds: str) -> str:
    ids = [
        next(row["id"] for row in rows(value) if row["type"] == kind) for kind in kinds
    ]
    return json.dumps({"observation_ids": ids})


def recheck(state: Snapshot) -> Snapshot:
    checks, evidence = evaluate(
        state.selected_date,
        day=Entity(kind="day", id=str(state.selected_date)),
        activities=state.activities,
        dogs=state.dogs,
        actual=state.actual,
        locations=state.locations,
        plan_exists=state.plan_exists,
    )
    return state.model_copy(update={"checks": checks, "evidence": evidence})


@pytest.mark.parametrize(
    "status,phrase",
    [
        ("not_recorded", "Actual work has not been recorded."),
        ("not_run", "The activity is marked as not run."),
        ("matches_plan", "Recorded work matches the saved plan."),
        ("modified", "Recorded work differs from the saved plan."),
        ("context_only", "This is a context-only activity;"),
    ],
)
def test_actual_status_comes_from_explicit_dated_state_not_check_pass(
    status: str,
    phrase: str,
) -> None:
    state = context_snapshot(with_actual=status in {"matches_plan", "modified"})
    activity = state.activities[0].model_copy(update={"actual_status": status})
    state = recheck(state.model_copy(update={"activities": (activity,)}))
    value = catalog(state)
    result = value.select(select(value, "actual_status"))
    assert phrase in result.answer.explanation
    assert result.answer.explanation == "".join(
        x.text for x in result.presentation.segments
    )
    assert result.presentation.status == "ready"
    assert len(result.presentation.observations) == 1
    assert result.presentation.observations[0].segments == result.presentation.segments
    if status == "not_recorded":
        assert (
            "Whether the activity took place is not established"
            in result.answer.explanation
        )
        assert "did not occur" not in result.answer.explanation
        assert "cancelled" not in result.answer.explanation
        assert "marked as not run" not in result.answer.explanation
    if status in {"not_run", "context_only"}:
        assert "matches the saved plan" not in result.answer.explanation
        assert (
            next(x for x in state.checks if x.rule == "ACTUAL_RECORDING").status
            == "pass"
        )
    FrozenTools(state).validate_references(result.answer.model_dump_json())


def test_context_activity_does_not_become_training_actual_work() -> None:
    state = context_snapshot()
    activity = state.activities[0].model_copy(
        update={"kind": "rest", "distance_km": None, "actual_status": "context_only"}
    )
    state = recheck(state.model_copy(update={"activities": (activity,)}))
    value = catalog(state)
    result = value.select(select(value, "actual_status"))
    assert result.answer.explanation.startswith("Rest — activity 1:")
    assert "not a Training actual-work confirmation" in result.answer.explanation
    assert not any(row["type"] == "saved_teams" for row in rows(value))


def test_empty_day_reports_saved_records_without_claiming_zero_events_occurred() -> (
    None
):
    state = context_snapshot(activity_count=0, pool_size=0)
    value = catalog(state)
    result = value.select(select(value, "plan_presence", "actual_totals"))
    assert "No saved plan exists" in result.answer.explanation
    assert "0 recorded sessions" in result.answer.explanation
    assert (
        "do not establish whether unrecorded activity took place"
        in result.answer.explanation
    )
    assert not any(row["type"] == "actual_status" for row in rows(value))


def test_selected_pool_teams_actual_and_safety_are_independent() -> None:
    value = catalog(context_snapshot())
    result = value.select(
        select(value, "selected_pool", "saved_teams", "actual_status", "eligibility")
    )
    assert "selected pool contains 4 dogs" in result.answer.explanation
    assert "No teams are saved" in result.answer.explanation
    assert "Actual work has not been recorded" in result.answer.explanation
    assert "not a medical or training-safety assessment" in result.answer.explanation
    assert "everything is fine" not in result.answer.explanation.lower()
    value = catalog(context_snapshot(with_team=True, with_actual=True))
    result = value.select(
        select(value, "selected_pool", "saved_teams", "actual_status", "actual_totals")
    )
    assert "1 team is saved" in result.answer.explanation
    assert "Recorded work matches the saved plan" in result.answer.explanation
    assert "1 recorded sessions" in result.answer.explanation


def test_omitted_details_do_not_generate_unissued_activity_observations() -> None:
    state = context_snapshot(activity_count=32, pool_size=4, missing_eligibility=True)
    result = tool_result(state)
    data = json.loads(result.data_json)
    value = catalog(state)
    assert len(rows(value)) <= MAX_OBSERVATIONS
    assert len(value.provider_json().encode()) <= MAX_CATALOG_BYTES
    admitted = {row["id"] for row in data["plan"]["activities"]}
    selected = value.select(
        json.dumps({"observation_ids": [row["id"] for row in rows(value)[:6]]})
    )
    assert all(
        ref.entity.kind != "activity" or ref.entity.id in admitted
        for ref in selected.answer.references
    )
    assert (
        data["plan"]["omitted_activity_count"] > 0 or data["omitted_detail_count"] > 0
    )
    assert "everything is fine" not in selected.answer.explanation.lower()


def test_unknown_actual_metrics_stay_unknown_not_zero() -> None:
    state = context_snapshot()
    actual_evidence = {
        identity
        for check in state.checks
        if check.rule == "ACTUAL_LEDGER"
        for identity in check.evidence_ids
    }
    state = state.model_copy(
        update={
            "checks": tuple(x for x in state.checks if x.rule != "ACTUAL_LEDGER"),
            "evidence": tuple(x for x in state.evidence if x.id not in actual_evidence),
        }
    )
    value = catalog(state)
    assert not any(row["type"] == "actual_totals" for row in rows(value))
    result = value.select(select(value, "qualification"))
    assert "omitted or not verified" in result.answer.explanation
    assert "0 recorded" not in result.answer.explanation
    assert json.loads(tool_result(state).data_json)["actual"]["sessions"] is None


@pytest.mark.parametrize(
    "extra",
    ["explanation", "reason", "title", "action_text", "url", "references", "scope"],
)
def test_model_free_text_or_reference_auxiliary_fields_are_rejected(extra: str) -> None:
    value = catalog()
    payload = json.loads(select(value, "actual_status"))
    payload[extra] = "PRIVATE_ARBITRARY_TEXT_NEVER_RENDER https://evil.invalid"
    with pytest.raises(OperationError, match="^invalid_selection$") as caught:
        value.select(json.dumps(payload))
    assert "PRIVATE_ARBITRARY" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"observation_ids": []},
        {"observation_ids": "o-known"},
        {"observation_ids": [1]},
        {"observation_ids": [None]},
        {"observation_ids": ["unknown"] * 7},
    ],
)
def test_invalid_selection_shape_is_not_repaired(payload: object) -> None:
    with pytest.raises(OperationError, match="^invalid_selection$"):
        catalog().select(json.dumps(payload))


def test_duplicate_unknown_stale_and_cross_snapshot_ids_are_not_repaired() -> None:
    state = context_snapshot()
    value = catalog(state)
    identity = rows(value)[0]["id"]
    with pytest.raises(OperationError, match="^invalid_selection$"):
        value.select(json.dumps({"observation_ids": [identity, identity]}))
    for other in (
        "o-unissued",
        rows(catalog(state, run="another-run"))[0]["id"],
        rows(catalog(state.model_copy(update={"id": uuid4()})))[0]["id"],
    ):
        with pytest.raises(OperationError, match="^invalid_evidence$"):
            value.select(json.dumps({"observation_ids": [other]}))


def test_wrong_scope_internal_catalog_mutation_is_detected_without_rebinding_id() -> (
    None
):
    value = catalog()
    original = value._observations[0]
    value._observations = (
        replace(original, scope="other_snapshot_dogs"),
        *value._observations[1:],
    )
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        value.select(json.dumps({"observation_ids": [original.id]}))


@pytest.mark.parametrize(
    "field",
    ["actual_status", "selected_pool_count", "kind", "distance_km", "evidence_ids"],
)
def test_forged_activity_tool_result_field_fails_same_snapshot_verification(
    field: str,
) -> None:
    state = context_snapshot()
    result = tool_result(state)
    data = json.loads(result.data_json)
    data["plan"]["activities"][0][field] = {
        "actual_status": "not_run",
        "selected_pool_count": 0,
        "kind": "rest",
        "distance_km": 10,
        "evidence_ids": ["e-forged"],
    }[field]
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        ObservationCatalog(
            state,
            result.model_copy(update={"data_json": json.dumps(data)}),
            "same-run",
            FrozenTools(state).link,
        )


@pytest.mark.parametrize(
    "mutation",
    ["scope", "evidence", "dog_state", "actual_metric", "omitted", "count_type"],
)
def test_forged_scope_evidence_state_and_unknown_aggregates_fail(mutation: str) -> None:
    state = context_snapshot()
    result = tool_result(state)
    data = json.loads(result.data_json)
    if mutation == "scope":
        data["checks"][0]["scope"] = "other_snapshot_dogs"
    elif mutation == "evidence":
        data["evidence"][0]["selected_date"] = "2026-03-28"
    elif mutation == "dog_state":
        data["selected_dog_states"][0]["lifecycle"] = "archived"
    elif mutation == "actual_metric":
        data["actual"]["sessions"] = None
    elif mutation == "count_type":
        data["status_counts"]["pass"] = True
    else:
        data["omitted_detail_count"] = 0
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        ObservationCatalog(
            state,
            result.model_copy(update={"data_json": json.dumps(data)}),
            "same-run",
            FrozenTools(state).link,
        )


def test_names_are_frozen_plain_text_links_are_server_owned_and_ids_never_visible() -> (
    None
):
    state = context_snapshot()
    names = ("Атлас <img src=x onerror=alert(1)>", "Aurora", "Same name", "Same name")
    state = state.model_copy(
        update={
            "dogs": tuple(
                dog.model_copy(update={"name": names[i]}) if i < len(names) else dog
                for i, dog in enumerate(state.dogs)
            )
        }
    )
    value = catalog(state)
    dog_entries = [row for row in rows(value) if row["type"] == "selected_dog_state"]
    result = value.select(
        json.dumps({"observation_ids": [row["id"] for row in dog_entries]})
    )
    assert names[0] in result.answer.explanation
    assert result.answer.explanation.count("Same name") == 2
    assert all(
        identity["id"] not in result.answer.explanation for identity in rows(value)
    )
    links = [
        segment
        for segment in result.presentation.segments
        if segment.entity is not None
    ]
    assert [x.text for x in links] == list(names)
    assert all(
        x.path == f"/demo/dogs/{x.entity.id}?tab=work"
        for x in links
        if x.entity is not None
    )
    assert "<img" in links[0].text  # Data text; Angular interpolation escapes it.
    assert not any(name in value.provider_json() for name in names)
    assert result.answer.explanation == "".join(
        x.text for x in result.presentation.segments
    )
    FrozenTools(state).validate_references(result.answer.model_dump_json())


def test_model_selection_and_order_change_visible_observations() -> None:
    value = catalog()
    first = value.select(select(value, "actual_status", "saved_teams"))
    second = value.select(select(value, "saved_teams", "actual_status"))
    different = value.select(select(value, "selected_pool"))
    assert (
        first.answer.explanation
        != second.answer.explanation
        != different.answer.explanation
    )
    assert first.answer.explanation.index(
        "has not been recorded"
    ) < first.answer.explanation.index("No teams")
    assert second.answer.explanation.index(
        "No teams"
    ) < second.answer.explanation.index("has not been recorded")


def test_current_evidence_kind_and_safe_local_link_are_required() -> None:
    state = context_snapshot()
    result = tool_result(state)
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        ObservationCatalog(
            state, result, "one-run", lambda _: "https://evil.invalid/redirect"
        )
    data = json.loads(result.data_json)
    dog = data["selected_dog_states"][0]
    dog["evidence_ids"] = data["plan"]["evidence_ids"]
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        ObservationCatalog(
            state,
            result.model_copy(update={"data_json": json.dumps(data)}),
            "one-run",
            FrozenTools(state).link,
        )


def test_result_wrong_tool_or_date_or_snapshot_never_creates_catalog() -> None:
    state = context_snapshot()
    result = tool_result(state)
    for changes in (
        {"tool": "get_day_plan"},
        {"snapshot_id": uuid4()},
        {"selected_date": date(2026, 3, 28)},
    ):
        with pytest.raises(OperationError, match="^invalid_evidence$"):
            ObservationCatalog(
                state,
                result.model_copy(update=changes),
                "one-run",
                FrozenTools(state).link,
            )


def test_seven_valid_ids_exceed_selection_limit_and_nonfinite_json_never_repairs() -> (
    None
):
    value = catalog()
    ids = [row["id"] for row in rows(value)[:7]]
    assert len(set(ids)) == 7
    with pytest.raises(OperationError, match="^invalid_selection$"):
        value.select(json.dumps({"observation_ids": ids}))
    for content in (
        '{"observation_ids":[],"observation_ids":[]}',
        '{"observation_ids":[],"reason":NaN}',
    ):
        with pytest.raises(OperationError, match="^invalid_selection$"):
            value.select(content)


def test_nonhashable_evidence_id_is_typed_safe_failure() -> None:
    value = catalog()
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        value._check_ids([{"id": "not-a-string"}], Entity(kind="day", id="2026-03-29"))


@pytest.mark.parametrize(
    "suffix", ["%0A", "%2F%2Fevil.invalid", "#section", "\\other", " "]
)
def test_changed_or_encoded_link_is_not_accepted_as_canonical(suffix: str) -> None:
    state = context_snapshot()
    link = FrozenTools(state).link
    with pytest.raises(OperationError, match="^invalid_evidence$"):
        ObservationCatalog(
            state, tool_result(state), "same-run", lambda entity: link(entity) + suffix
        )


def test_display_never_mutates_snapshot_or_result() -> None:
    state = context_snapshot()
    result = tool_result(state)
    before_state, before_result = state.model_dump_json(), result.model_dump_json()
    value = ObservationCatalog(state, result, "same-run", FrozenTools(state).link)
    for ids in (
        [x["id"] for x in rows(value)[:3]],
        [x["id"] for x in rows(value)[3:6]],
    ):
        value.select(json.dumps({"observation_ids": ids}))
    assert state.model_dump_json() == before_state
    assert result.model_dump_json() == before_result
