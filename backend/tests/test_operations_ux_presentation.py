"""UX-GROQ structural presentation over detached frozen facts; no live inference."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError
from test_operations_display import state
from test_operations_observations import catalog, recheck, rows, select

from app.operations.api_schemas import ReviewDisplay, ReviewDisplaySegment, ReviewTrace
from app.operations.display import FrozenDisplay
from app.operations.foundation import PreparedReview
from app.operations.provider_models import Usage
from app.operations.review import OperationsReviewService
from app.operations.schemas import Entity
from app.operations.tools import FrozenTools


def test_observation_boundaries_preserve_model_order_and_bound_references() -> None:
    snapshot = state(activity_count=2)
    before = snapshot.model_dump_json()
    value = catalog(snapshot)
    selected_ids = [row["id"] for row in rows(value) if row["type"] == "actual_status"][
        ::-1
    ]
    rendered = value.select(json.dumps({"observation_ids": selected_ids}))
    assert len(rendered.presentation.observations) == 2
    ordered_segments = []
    for index, observation in enumerate(rendered.presentation.observations):
        assert observation.segments
        if index:
            ordered_segments.append(ReviewDisplaySegment(text=" "))
        ordered_segments.extend(observation.segments)
    # Equality includes typed identity and canonical path, not only visible text.
    assert tuple(ordered_segments) == rendered.presentation.segments
    assert rendered.answer.explanation == "".join(x.text for x in ordered_segments)
    assert [
        observation.segments[0].text
        for observation in rendered.presentation.observations
    ] == ["Training · 5 km — activity 2", "Training · 5 km — activity 1"]
    assert [
        observation.segments[0].entity.id
        for observation in rendered.presentation.observations
    ] == [str(row.id) for row in reversed(snapshot.activities)]
    tools = FrozenTools(snapshot)
    tools.validate_references(rendered.answer.model_dump_json())
    assert all(
        segment.path == tools.link(segment.entity)
        for segment in rendered.presentation.segments
        if segment.entity is not None
    )
    assert not any(
        str(row.id) in rendered.answer.explanation for row in snapshot.activities
    )
    assert snapshot.model_dump_json() == before


@pytest.mark.parametrize("kind", ["rest", "open_space_walk", "individual_exercise"])
def test_context_pool_uses_neutral_activity_text_without_harness_claim(
    kind: str,
) -> None:
    snapshot = state(pool_size=2)
    activity = snapshot.activities[0].model_copy(
        update={"kind": kind, "distance_km": None, "actual_status": "context_only"}
    )
    snapshot = recheck(snapshot.model_copy(update={"activities": (activity,)}))
    value = catalog(snapshot)
    rendered = value.select(select(value, "selected_pool", "actual_status"))
    assert "2 dogs selected for this planned activity." in rendered.answer.explanation
    assert "saved teams" not in rendered.answer.explanation
    assert "harness" not in rendered.answer.explanation
    assert "context-only activity" in rendered.answer.explanation
    assert "not a Training actual-work confirmation" in rendered.answer.explanation
    assert len(rendered.presentation.observations) == 2
    assert not any(row["type"] == "saved_teams" for row in rows(value))


def test_legacy_flat_presentation_remains_compatible_without_invented_boundaries() -> (
    None
):
    flat = ReviewDisplay(
        status="ready", segments=(ReviewDisplaySegment(text="One fact."),)
    )
    assert flat.observations == ()
    assert ReviewDisplay.model_validate_json(flat.model_dump_json()) == flat
    assert (
        ReviewDisplay.model_validate_json(
            '{"status":"ready","segments":[{"text":"One fact."}],"message":null}'
        )
        == flat
    )
    grouped = ReviewDisplay.model_validate_json(
        json.dumps(
            {
                "status": "ready",
                "segments": [{"text": "One fact."}],
                "observations": [{"segments": [{"text": "One fact."}]}],
            }
        )
    )
    assert grouped.segments == flat.segments
    assert len(grouped.observations) == 1


@pytest.mark.parametrize("malformation", ["text", "entity", "path", "empty", "status"])
def test_mismatched_structural_metadata_is_rejected(malformation: str) -> None:
    segment = {
        "text": "Training · 5 km — activity 1",
        "entity": {"kind": "activity", "id": "bound-identity"},
        "path": "/demo/daily?date=2026-03-29",
    }
    value = {
        "status": "ready",
        "segments": [segment],
        "observations": [{"segments": [dict(segment)]}],
    }
    # Prove the original fixture is valid before introducing each mismatch.
    assert ReviewDisplay.model_validate_json(json.dumps(value)).observations
    changed = value["observations"][0]["segments"]
    if malformation == "text":
        changed[0]["text"] = "A different statement"
    elif malformation == "entity":
        changed[0]["entity"] = {"kind": "activity", "id": "another-identity"}
    elif malformation == "path":
        changed[0]["path"] = "/demo/daily-entry?date=2026-03-29"
    elif malformation == "empty":
        changed.clear()
    else:
        value["status"] = "unresolved"
    with pytest.raises(ValidationError):
        ReviewDisplay.model_validate_json(json.dumps(value))


def test_same_distance_activities_have_frozen_labels_and_neutral_dated_team_links() -> (
    None
):
    snapshot = state(activity_count=2)
    tools = FrozenTools(snapshot)
    display = FrozenDisplay(snapshot, tools.link)
    expected = ["Training · 5 km — activity 1", "Training · 5 km — activity 2"]
    assert [row.label for row in display.summary().activities] == expected
    assert display.activity_label("not-in-this-snapshot") is None
    value = catalog(snapshot)
    rendered = value.select(select(value, "plan_presence"))
    prepared = cast(
        PreparedReview,
        SimpleNamespace(
            context=SimpleNamespace(snapshot=snapshot),
            tools=tools,
            run=SimpleNamespace(
                quota_retries=0,
                metadata=lambda: SimpleNamespace(
                    provider="groq",
                    model="openai/gpt-oss-20b",
                    switches=0,
                    http_calls=2,
                    tool_calls=1,
                    known_run_usage=Usage(prompt_tokens=10, completion_tokens=5),
                    usage_complete=True,
                ),
            ),
        ),
    )
    response = OperationsReviewService._response(
        prepared,
        rendered,
        (ReviewTrace(tool_name="validate_day", provider="groq", elapsed_ms=1),),
    )
    activity_links = [row for row in response.links if row.entity.kind == "activity"]
    assert [row.label for row in activity_links] == ["Teams for " + x for x in expected]
    assert [row.path for row in activity_links] == [
        tools.link(Entity(kind="activity", id=str(row.id)))
        for row in snapshot.activities
    ]
    assert all(
        "2026-03-29" in row.path and row.path.endswith("/teams")
        for row in activity_links
    )
    assert all(row.saved_teams == 0 for row in response.summary.activities)
    assert [
        check.entities[0].id
        for check in response.findings
        if check.rule == "SAVED_LINEUP"
    ] == [str(row.id) for row in snapshot.activities]
    assert response.findings == tuple(
        check for group in display.finding_groups() for check in group.findings
    )

    # No later plan/snapshot change is refetched into an already-built display.
    changed = snapshot.model_copy(
        update={
            "activities": (
                snapshot.activities[0].model_copy(update={"distance_km": 10}),
                snapshot.activities[1],
            )
        }
    )
    assert (
        FrozenDisplay(changed, FrozenTools(changed).link).activity_label(
            str(changed.activities[0].id)
        )
        == "Training · 10 km — activity 1"
    )
    assert [row.label for row in response.summary.activities] == expected
    assert [row.label for row in display.summary().activities] == expected
