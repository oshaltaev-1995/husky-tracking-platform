"""Detached presentation/operational facts; no provider, database, or key file.

These fixtures establish deterministic labels and metric semantics, not the truth
of arbitrary generated prose. Genuine model quality is a separate bounded QA gate.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from test_operations_tools import context_snapshot

from app.operations.api_schemas import ReviewTrace
from app.operations.checks import evaluate
from app.operations.display import FrozenDisplay
from app.operations.foundation import PreparedReview
from app.operations.provider_models import Usage
from app.operations.review import OperationsReviewService
from app.operations.schemas import Entity, Snapshot
from app.operations.tools import FrozenTools


def state(**changes: object) -> Snapshot:
    source = context_snapshot(**changes)  # type: ignore[arg-type]
    names = ("Atlas", "Aurora", "Clover", "Cosmo")
    return source.model_copy(
        update={
            "dogs": tuple(
                dog.model_copy(update={"name": names[index]})
                if index < len(names)
                else dog
                for index, dog in enumerate(source.dogs)
            )
        }
    )


def display(snapshot: Snapshot) -> FrozenDisplay:
    return FrozenDisplay(snapshot, FrozenTools(snapshot).link)


def flattened(result: object) -> str:
    return "".join(part.text for part in result.segments)  # type: ignore[attr-defined]


def test_four_dog_groq_regression_names_replace_ids_without_rewriting_claims() -> None:
    frozen = state()
    ids = [str(dog.id) for dog in frozen.dogs[:4]]
    text = (
        "The snapshot reports one planned activity of 5 km on 2026-03-29 with "
        f"four eligible dogs (IDs {', '.join(ids)}). No actual sessions were "
        "recorded (sessions 0, dog_km 0). The selected pool is distinct from "
        "any saved team."
    )
    before = frozen.model_dump_json()
    result = display(frozen).explanation(text)
    assert result.status == "ready" and result.message is None
    assert flattened(result) == text.replace(
        "IDs " + ", ".join(ids), "Atlas, Aurora, Clover, Cosmo"
    )
    assert frozen.model_dump_json() == before
    # Case is a UUID representation detail, not a new identity or evidence repair.
    # Use a hexadecimal-letter identity so this is a genuine uppercase regression.
    mixed_case_id = str(frozen.dogs[9].id).upper()
    assert mixed_case_id != str(frozen.dogs[9].id)
    uppercase = display(frozen).explanation(f"Dog {mixed_case_id}.")
    mention = next(part for part in uppercase.segments if part.entity is not None)
    assert uppercase.status == "ready" and mention.text == frozen.dogs[9].name
    assert mention.entity == Entity(kind="dog", id=str(frozen.dogs[9].id))
    assert mention.path == f"/demo/dogs/{frozen.dogs[9].id}?tab=work"
    assert frozen.model_dump_json() == before
    links = [part for part in result.segments if part.entity is not None]
    assert [part.entity.id for part in links] == ids
    assert [part.path for part in links] == [
        f"/demo/dogs/{identity}?tab=work" for identity in ids
    ]
    assert all(identity not in flattened(result) for identity in ids)
    summary = display(frozen).summary()
    activity = summary.activities[0]
    assert activity.kind == "training" and activity.distance_km == 5
    assert activity.selected_pool_count == 4
    assert [link.label for link in activity.selected_dogs] == [
        "Atlas",
        "Aurora",
        "Clover",
        "Cosmo",
    ]
    assert activity.saved_teams == 0 and activity.actual_status == "not_recorded"
    assert (
        summary.actual.sessions
        == summary.actual.dog_starts
        == summary.actual.dog_km
        == 0
    )


def test_mentions_repeat_and_exact_typed_entities_keep_distinct_local_identity() -> (
    None
):
    frozen = state(with_actual=True)
    first = str(frozen.dogs[0].id)
    activity = str(frozen.activities[0].id)
    actual = str(frozen.actual[0].id)
    text = f"Dog {first}; again {first}. Activity {activity}. Session {actual}. 30 km."
    result = display(frozen).explanation(text)
    assert result.status == "ready"
    assert flattened(result) == (
        "Dog Atlas; again Atlas. Activity Training · activity 1. "
        "Session Recorded work. 30 km."
    )
    assert [part.entity.kind for part in result.segments if part.entity] == [
        "dog",
        "dog",
        "activity",
        "actual",
    ]
    assert display(frozen).explanation(f"Activity {first}").status == "unresolved"
    assert display(frozen).explanation(f"Dog {activity}").status == "unresolved"
    ambiguous = frozen.model_copy(
        update={
            "activities": (
                frozen.activities[0].model_copy(update={"id": frozen.dogs[0].id}),
            )
        }
    )
    assert display(ambiguous).explanation(first).status == "unresolved"


def test_unknown_malformed_or_embedded_identity_is_unresolved() -> None:
    frozen = state()
    known = str(frozen.dogs[0].id)
    for text in [
        f"Dog {UUID(int=99999)} was selected.",
        "Dog 00000000-0000-0000-0000-00000000000Z was selected.",
        f"Dog prefix{known}suffix was selected.",
    ]:
        result = display(frozen).explanation(text)
        assert result.status == "unresolved" and result.segments == ()
        assert result.message and "could not be matched" in result.message
        assert str(UUID(int=99999)) not in result.message
    empty = display(frozen).explanation("  ")
    assert empty.status == "unresolved" and empty.segments == ()
    assert empty.message and "empty" in empty.message
    # Dates, quantities and words are not identities and are not reformatted.
    text = "No training on 2026-03-29. 4 dogs, 5 km, 30 km limit."
    assert flattened(display(frozen).explanation(text)) == text


def test_duplicate_cyrillic_and_html_names_keep_plain_text_links() -> None:
    frozen = state()
    names = (
        "Nova",
        "Nova",
        "Северная Звезда " + "а" * 95,
        '<img src=x onerror="bad()">',
    )
    dogs = tuple(
        dog.model_copy(
            update={"name": names[index], "housing_code": f"A1-0{index + 1}"}
        )
        if index < 4
        else dog
        for index, dog in enumerate(frozen.dogs)
    )
    frozen = frozen.model_copy(update={"dogs": dogs})
    result = display(frozen).explanation(
        ", ".join(str(dog.id) for dog in frozen.dogs[:4])
    )
    assert result.status == "ready"
    parts = [part for part in result.segments if part.entity]
    assert [part.entity.id for part in parts] == [str(dog.id) for dog in dogs[:4]]
    assert parts[0].text == "Nova · A1-01 · standard"
    assert parts[1].text == "Nova · A1-02 · standard"
    assert parts[0].path != parts[1].path
    assert parts[2].text == names[2] and parts[3].text == names[3]
    assert all(part.entity.kind == "dog" for part in parts)
    # These are ordinary text DTOs, never HTML or model-created destinations.
    assert all(part.path.startswith("/demo/dogs/") for part in parts)
    assert not any("Dog 1" in part.text for part in parts)


def test_empty_plan_and_recorded_actual_are_independent_snapshot_facts() -> None:
    empty = display(state(activity_count=0, pool_size=0)).summary()
    assert empty.plan_exists is False and empty.activities == ()
    assert empty.selected_unique_dogs == empty.selected_participations == 0
    assert empty.actual.sessions == empty.actual.dog_starts == empty.actual.dog_km == 0
    actual_only = display(state(activity_count=0, with_actual=True)).summary()
    assert actual_only.plan_exists is False and actual_only.activities == ()
    assert actual_only.selected_unique_dogs == 0
    assert actual_only.actual.sessions == 1
    assert actual_only.actual.dogs_worked == actual_only.actual.dog_starts == 4
    assert actual_only.actual.dog_km == 40
    not_run = state()
    not_run = not_run.model_copy(
        update={
            "activities": (
                not_run.activities[0].model_copy(update={"actual_status": "not_run"}),
            )
        }
    )
    summary = display(not_run).summary()
    assert (
        summary.activities[0].actual_status == "not_run"
        and summary.actual.sessions == 0
    )


def test_saved_teams_do_not_imply_actual_and_repeated_dogs_are_not_double_counted() -> (
    None
):
    summary = display(state(activity_count=2, with_team=True)).summary()
    assert summary.activity_count == 2
    assert summary.selected_unique_dogs == 4 and summary.selected_participations == 8
    assert [activity.saved_teams for activity in summary.activities] == [1, 1]
    assert all(
        activity.actual_status == "not_recorded" for activity in summary.activities
    )
    assert summary.actual.sessions == summary.actual.dog_km == 0
    frozen = state(with_actual=True)
    frozen = frozen.model_copy(update={"actual": (frozen.actual[0], frozen.actual[0])})
    actual = display(frozen).summary().actual
    assert actual.sessions == 2 and actual.dogs_worked == 4
    assert actual.dog_starts == 8 and actual.dog_km == 80


def test_selected_archived_problem_primary_but_unselected_archives_secondary() -> None:
    frozen = state(selected_archived=True)
    primary, other = display(frozen).finding_groups()
    selected = {str(identity) for identity in frozen.activities[0].participants}
    assert primary.scope == "plan" and other.scope == "other_dogs"
    assert any(row.rule == "PARTICIPANT_ELIGIBILITY" for row in primary.findings)
    assert any(
        row.rule == "DOG_STATE"
        and any(entity.id == str(frozen.dogs[-1].id) for entity in row.entities)
        for row in primary.findings
    )
    assert all(link.entity.id in selected for link in primary.links)
    assert all(link.entity.id not in selected for link in other.links)
    assert all(
        all(entity.id not in selected for entity in row.entities)
        for row in other.findings
    )
    normal_primary, normal_other = display(state()).finding_groups()
    assert normal_primary.status_counts.unverified == 0
    assert normal_other.status_counts.unverified == 10


def test_missing_dated_state_and_missing_dog_name_remain_explicit_not_zero() -> None:
    frozen = state()
    dogs = (
        frozen.dogs[0].model_copy(update={"dog_class": None, "housing_code": None}),
        *frozen.dogs[1:],
    )
    checks, evidence = evaluate(
        frozen.selected_date,
        day=Entity(kind="day", id=str(frozen.selected_date)),
        activities=frozen.activities,
        dogs=dogs,
        actual=frozen.actual,
        locations=frozen.locations,
        plan_exists=frozen.plan_exists,
    )
    frozen = frozen.model_copy(
        update={"dogs": dogs, "checks": checks, "evidence": evidence}
    )
    primary, _ = display(frozen).finding_groups()
    assert any(row.rule == "DATED_STATE_MISSING" for row in primary.findings)
    missing = frozen.model_copy(update={"dogs": frozen.dogs[1:]})
    summary = display(missing).summary()
    assert summary.activities[0].selected_pool_count == 4
    assert len(summary.activities[0].selected_dogs) == 3
    assert summary.activities[0].omitted_selected_dogs == 1
    assert display(missing).explanation(str(frozen.dogs[0].id)).status == "unresolved"


def test_large_snapshot_omissions_are_truthful_and_frozen() -> None:
    frozen = state(activity_count=32, pool_size=60, dog_count=60)
    before = frozen.model_dump_json()
    summary = display(frozen).summary()
    groups = display(frozen).finding_groups()
    assert len(summary.activities) == 32 and summary.omitted_activities == 0
    assert (
        summary.selected_unique_dogs == 60 and summary.selected_participations == 1920
    )
    assert all(len(activity.selected_dogs) == 60 for activity in summary.activities)
    nonpass = [row for row in frozen.checks if row.status != "pass"]
    assert sum(len(group.findings) for group in groups) <= 32
    assert sum(group.omitted_findings for group in groups) == len(nonpass) - sum(
        len(group.findings) for group in groups
    )
    assert len(summary.model_dump_json().encode()) < 500_000
    assert frozen.model_dump_json() == before


def test_response_keeps_verified_facts_when_explanation_cannot_be_presented() -> None:
    frozen = state()
    tools = FrozenTools(frozen)
    evidence = frozen.evidence[0]
    answer = tools.validate_references(
        json.dumps(
            {
                "explanation": f"Dog {UUID(int=99999)} was selected.",
                "references": [
                    {
                        "snapshot_id": str(frozen.id),
                        "selected_date": str(frozen.selected_date),
                        "evidence_id": evidence.id,
                        "entity": evidence.entities[0].model_dump(),
                    }
                ],
            }
        )
    )
    prepared = cast(
        PreparedReview,
        SimpleNamespace(
            context=SimpleNamespace(snapshot=frozen),
            tools=tools,
            run=SimpleNamespace(
                metadata=lambda: SimpleNamespace(
                    provider="groq",
                    model="openai/gpt-oss-20b",
                    switches=0,
                    http_calls=2,
                    tool_calls=1,
                    known_run_usage=Usage(prompt_tokens=12, completion_tokens=10),
                    usage_complete=True,
                )
            ),
        ),
    )
    result = OperationsReviewService._response(
        prepared,
        answer,
        (ReviewTrace(tool_name="validate_day", provider="groq", elapsed_ms=1),),
    )
    assert (
        result.presentation.status == "unresolved"
        and result.presentation.segments == ()
    )
    assert result.summary.activities[0].selected_pool_count == 4
    assert len(result.facts) == 2
    assert all(link.entity.kind != "dog" for link in result.links)
    assert sum(len(group.findings) for group in result.finding_groups) == len(
        result.findings
    )
    # Display mapping does not modify or manufacture claim/evidence references.
    assert answer.references[0].entity == evidence.entities[0]
