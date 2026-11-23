"""Detached presentation/operational facts; no provider, database, or key file.

These fixtures establish deterministic labels and metric semantics, not the truth
of arbitrary generated prose. Genuine model quality is a separate bounded QA gate.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from test_operations_tools import context_snapshot

from app.operations.api_schemas import ReviewTrace
from app.operations.checks import evaluate
from app.operations.display import FrozenDisplay
from app.operations.foundation import PreparedReview
from app.operations.provider_models import Usage
from app.operations.review import OperationsReviewService
from app.operations.schemas import ClaimReference, Entity, Snapshot
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


@pytest.mark.parametrize(
    "separators",
    [
        "-",
        "\u2010",
        "\u2011",
        "\u2012",
        "\u2013",
        "\u2014",
        "\u2015",
        "\u2212",
        "\ufe63",
        "\uff0d",
        "-\u2011\u2013\u2212",
    ],
)
def test_unicode_uuid_candidates_resolve_only_from_frozen_entities(
    separators: str,
) -> None:
    frozen = state()
    before = frozen.model_dump_json()

    def represented(identity: UUID) -> str:
        groups = str(identity).upper().split("-")
        return groups[0] + "".join(
            separators[index % len(separators)] + group
            for index, group in enumerate(groups[1:])
        )

    ids = [represented(dog.id) for dog in frozen.dogs[:4]]
    text = (
        f"Selected dogs (IDs {ids[0]}, {ids[1]}, {ids[2]}, and {ids[3]}). "
        f"Dog {ids[0]} again. On 2026-03-29 — 4 dogs, 5–10 km, no actual work."
    )
    result = display(frozen).explanation(text)
    assert result.status == "ready"
    assert flattened(result) == (
        "Selected dogs (Atlas, Aurora, Clover, and Cosmo). Dog Atlas again. "
        "On 2026-03-29 — 4 dogs, 5–10 km, no actual work."
    )
    linked = [part for part in result.segments if part.entity]
    expected = [*frozen.dogs[:4], frozen.dogs[0]]
    assert [part.text for part in linked] == [dog.name for dog in expected]
    assert [part.entity.id for part in linked if part.entity] == [
        str(dog.id) for dog in expected
    ]
    assert [part.path for part in linked] == [
        f"/demo/dogs/{dog.id}?tab=work" for dog in expected
    ]
    assert frozen.model_dump_json() == before


def test_unicode_typed_entities_and_id_lists_do_not_guess_kind() -> None:
    frozen = state(with_actual=True)
    dog = str(frozen.dogs[0].id).replace("-", "\u2011")
    activity = str(frozen.activities[0].id).replace("-", "\u2212")
    actual = str(frozen.actual[0].id).replace("-", "\u2013")
    result = display(frozen).explanation(
        f"Dog {dog}; Activity {activity}; Session {actual}."
    )
    assert result.status == "ready"
    assert [part.entity.kind for part in result.segments if part.entity] == [
        "dog",
        "activity",
        "actual",
    ]
    for text in (
        f"Activity {dog}.",
        f"Dog {activity}.",
        f"Session {dog}.",
        f"Dog IDs {dog}, {activity}.",
        f"Dog IDs {dog}, and {actual}.",
    ):
        result = display(frozen).explanation(text)
        assert result.status == "unresolved" and not result.segments
    ambiguous = frozen.model_copy(
        update={
            "activities": (
                frozen.activities[0].model_copy(update={"id": frozen.dogs[0].id}),
            )
        }
    )
    assert display(ambiguous).explanation(dog).status == "unresolved"


@pytest.mark.parametrize(
    "control",
    [
        "\u00ad",
        "\u034f",
        "\u061c",
        "\u180e",
        "\u200b",
        "\u200d",
        "\u202e",
        "\u2066",
        "\ufeff",
    ],
)
def test_controls_inside_uuid_candidates_are_unresolved_not_repaired(
    control: str,
) -> None:
    frozen = state()
    known = str(frozen.dogs[0].id).replace("-", "\u2011")
    for position in (1, 8, 9, len(known) - 1):
        token = known[:position] + control * 12 + known[position:]
        result = display(frozen).explanation(f"Dog {token} — 5 km.")
        assert result.status == "unresolved" and result.segments == ()
        assert result.message and token not in result.message
    summary = display(frozen).summary()
    assert summary.activities[0].selected_pool_count == 4
    assert summary.activities[0].saved_teams == 0
    assert summary.activities[0].actual_status == "not_recorded"
    assert summary.actual.sessions == 0


def test_unicode_unknown_malformed_embedded_candidates_and_names_are_safe() -> None:
    frozen = state()
    known = str(frozen.dogs[0].id).replace("-", "\u2010")
    for token in (
        str(UUID(int=99999)).replace("-", "\u2013"),
        "00000000\u20110000-0000\u22120000\u201300000000000Z",
        "0000000\u20110000-0000\u22120000\u2013000000000000",
        f"prefix{known}suffix",
        f"prefix{known[:-1]}Zsuffix",
    ):
        result = display(frozen).explanation(f"Dog {token} is selected.")
        assert result.status == "unresolved" and not result.segments
    names = (
        "Север — Звезда",
        "Éclair",
        '<img src=x onerror="bad()">',
        "Север — Звезда",
    )
    frozen = frozen.model_copy(
        update={
            "dogs": tuple(
                dog.model_copy(update={"name": names[index]}) if index < 4 else dog
                for index, dog in enumerate(frozen.dogs)
            )
        }
    )
    result = display(frozen).explanation(
        ", ".join(str(dog.id).replace("-", "\u2011") for dog in frozen.dogs[:4])
    )
    assert result.status == "ready"
    linked = [part for part in result.segments if part.entity]
    assert linked[0].text.startswith(names[0]) and linked[3].text.startswith(names[3])
    assert linked[0].path != linked[3].path
    assert linked[1].text == names[1] and linked[2].text == names[2]
    assert all(part.path and part.path.startswith("/demo/dogs/") for part in linked)


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


@pytest.mark.parametrize(
    "raw_identity",
    [
        str(UUID(int=99999)),
        str(UUID(int=99999)).replace("-", "\u2011"),
        "00000000-0000\u200b-0000-0000-00000001869f",
    ],
)
def test_response_keeps_verified_facts_when_explanation_cannot_be_presented(
    raw_identity: str,
) -> None:
    frozen = state()
    tools = FrozenTools(frozen)
    evidence = frozen.evidence[0]
    answer = tools.validate_references(
        json.dumps(
            {
                "explanation": f"Dog {raw_identity} was selected.",
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
                quota_retries=0,
                metadata=lambda: SimpleNamespace(
                    provider="groq",
                    model="openai/gpt-oss-20b",
                    switches=0,
                    http_calls=2,
                    tool_calls=1,
                    known_run_usage=Usage(prompt_tokens=12, completion_tokens=10),
                    usage_complete=True,
                ),
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
    assert result.quota_retries == 0
    assert len(result.facts) == 2
    assert all(link.entity.kind != "dog" for link in result.links)
    assert sum(len(group.findings) for group in result.finding_groups) == len(
        result.findings
    )
    # Display mapping does not modify or manufacture claim/evidence references.
    assert answer.references[0].entity == evidence.entities[0]

    # The actual response path supplies executed trace and validated references,
    # while raw explanation and technical trace retain their existing contract.
    raw = f"validate_day did not record actual work; see {evidence.id}."
    accepted = answer.model_copy(update={"explanation": raw})
    presented = OperationsReviewService._response(
        prepared,
        accepted,
        (ReviewTrace(tool_name="validate_day", provider="groq", elapsed_ms=1),),
    )
    assert presented.explanation == raw and accepted.references == answer.references
    assert flattened(presented.presentation) == (
        "saved-day check did not record actual work; see saved-plan record."
    )
    assert presented.trace[0].tool_name == "validate_day"
    assert presented.facts == result.facts and presented.summary == result.summary
    assert presented.http_calls == 2 and presented.tool_calls == 1


# These exact prose fixtures are manually transcribed from the accepted recovery
# PNGs (22 Nov 2026), not captured HTTP payloads or new model responses. The empty
# case is intentionally not rewritten to improve its qualitative claims.
_P14C_GENUINE_EMPTY_TRANSCRIPTION = (
    "The validate_day tool reports that on 2026-03-29 no plan was present and no "
    "actual sessions or dog starts occurred. The evidence entries e-001 and "
    "e-144 both record the day entity with zero activities, sessions, dog starts, "
    "and distance. No dogs, activities, or actual work are indicated for that "
    "date. Thus the day’s operational snapshot contains no scheduled or "
    "completed work."
)
_P14C_GENUINE_FOUR_DOGS_TRANSCRIPTION = (
    "The snapshot for 2026-03-29 reports one planned activity (distance 5 km) with "
    "four selected dogs and no saved teams or recorded actual work. No actual "
    "sessions or distance were logged for that day. All data come directly from "
    "the server-issued evidence; no inference is made that the plan was "
    "executed. Selected dogs are listed in the plan’s selected pool and each "
    "has availability, born, lifecycle, class, and role attributes as provided "
    "by the evidence."
)
_P14C_GENUINE_ACTUAL_TRANSCRIPTION = (
    "The validated snapshot for 2026-03-31 reports zero planned activities and "
    "two actual training sessions involving 16 dog starts totaling 120 km. The "
    "plan check indicates no saved plan exists, so no inference of planned work "
    "can be made. All counts are based on the frozen snapshot; omitted details "
    "are unknown, not zero. No saved teams or dog state details are present."
)


def references_for(snapshot: Snapshot, *rules: str) -> tuple[ClaimReference, ...]:
    evidence_ids = {
        identity
        for check in snapshot.checks
        if check.rule in rules
        for identity in check.evidence_ids
    }
    return tuple(
        ClaimReference(
            snapshot_id=snapshot.id,
            selected_date=snapshot.selected_date,
            evidence_id=row.id,
            entity=row.entities[0],
        )
        for row in snapshot.evidence
        if row.id in evidence_ids
    )


def with_evidence_names(snapshot: Snapshot, names: dict[str, str]) -> Snapshot:
    return snapshot.model_copy(
        update={
            "evidence": tuple(
                row.model_copy(update={"id": names.get(row.id, row.id)})
                for row in snapshot.evidence
            ),
            "checks": tuple(
                check.model_copy(
                    update={
                        "evidence_ids": tuple(
                            names.get(identity, identity)
                            for identity in check.evidence_ids
                        )
                    }
                )
                for check in snapshot.checks
            ),
        }
    )


def test_genuine_empty_prose_labels_only_exact_executed_validated_tokens() -> None:
    frozen = state(activity_count=0, pool_size=0)
    plan = references_for(frozen, "PLAN_PRESENCE")[0]
    actual = references_for(frozen, "ACTUAL_LEDGER")[0]
    frozen = with_evidence_names(
        frozen, {plan.evidence_id: "e-001", actual.evidence_id: "e-144"}
    )
    original = frozen.model_dump_json()
    result = display(frozen).explanation(
        _P14C_GENUINE_EMPTY_TRANSCRIPTION,
        executed_tools=("validate_day",),
        references=references_for(frozen, "PLAN_PRESENCE", "ACTUAL_LEDGER"),
    )
    assert result.status == "ready"
    assert flattened(result) == (
        "The saved-day check tool reports that on 2026-03-29 no plan was present "
        "and no actual sessions or dog starts occurred. The evidence entries "
        "saved-plan record and recorded-work totals both record the day entity "
        "with zero activities, sessions, dog starts, and distance. No dogs, "
        "activities, or actual work are indicated for that date. Thus the day’s "
        "operational snapshot contains no scheduled or completed work."
    )
    assert all(part.path is None and part.entity is None for part in result.segments)
    assert frozen.model_dump_json() == original
    # No presentation layer inference that an empty plan means an empty kennel.
    assert len(frozen.dogs) == 14 and display(frozen).summary().plan_exists is False
    for text in (
        _P14C_GENUINE_FOUR_DOGS_TRANSCRIPTION,
        _P14C_GENUINE_ACTUAL_TRANSCRIPTION,
    ):
        assert flattened(display(frozen).explanation(text)) == text


def test_evidence_label_comes_from_check_not_ordinal_or_model_claim() -> None:
    frozen = state(with_actual=True)
    plan = references_for(frozen, "PLAN_PRESENCE")[0]
    actual = references_for(frozen, "ACTUAL_LEDGER")[0]
    frozen = with_evidence_names(
        frozen, {plan.evidence_id: "e-987", actual.evidence_id: "e-001"}
    )
    text = "e-001 reports 4 starts, 40 km; e-987 does not prove completion."
    result = display(frozen).explanation(
        text, references=references_for(frozen, "PLAN_PRESENCE", "ACTUAL_LEDGER")
    )
    assert flattened(result) == (
        "recorded-work totals reports 4 starts, 40 km; saved-plan record does "
        "not prove completion."
    )
    assert display(frozen).summary().actual.dog_starts == 4
    assert display(frozen).summary().actual.dog_km == 40
    # Known-but-unreferenced frozen evidence and known-but-unexecuted tools fail
    # closed, rather than becoming a verified looking label.
    assert display(frozen).explanation("e-987").status == "unresolved"
    assert display(frozen).explanation("validate_day").status == "unresolved"
    assert (
        display(frozen)
        .explanation("get_saved_teams", executed_tools=("validate_day",))
        .status
        == "unresolved"
    )
    assert display(frozen).explanation("e-999999").status == "unresolved"
    # Exact boundaries: dates/numbers and larger ordinary tokens are unchanged.
    literal = "prefixe-987suffix validate_day_extra 2026-03-29 16 starts / 120 dog-km."
    assert flattened(display(frozen).explanation(literal)) == literal


def test_ambiguous_or_stale_evidence_does_not_hide_trusted_summary() -> None:
    frozen = state()
    refs = references_for(frozen, "PLAN_PRESENCE")
    identity = refs[0].evidence_id
    duplicate_record = frozen.model_copy(
        update={"evidence": (*frozen.evidence, frozen.evidence[0])}
    )
    duplicate_check = frozen.model_copy(
        update={"checks": (*frozen.checks, frozen.checks[0])}
    )
    unknown_rule = frozen.model_copy(
        update={
            "checks": (
                frozen.checks[0].model_copy(update={"rule": "NEW_UNLABELLED_CHECK"}),
                *frozen.checks[1:],
            )
        }
    )
    stale_ref = refs[0].model_copy(update={"snapshot_id": UUID(int=55555)})
    wrong_entity = refs[0].model_copy(
        update={"entity": Entity(kind="dog", id=str(frozen.dogs[0].id))}
    )
    for source, references in [
        (duplicate_record, refs),
        (duplicate_check, refs),
        (unknown_rule, refs),
        (frozen, (stale_ref,)),
        (frozen, (wrong_entity,)),
    ]:
        result = display(source).explanation(identity, references=references)
        assert result.status == "unresolved" and result.segments == ()
        assert display(source).summary().activities[0].selected_pool_count == 4
        assert display(source).summary().activities[0].saved_teams == 0
        assert display(source).summary().actual.sessions == 0


def test_token_shaped_names_have_identity_priority_without_a_second_regex_pass() -> (
    None
):
    frozen = state()
    names = ("e-001", "validate_day", "validate_day", "<e-999>")
    frozen = frozen.model_copy(
        update={
            "dogs": tuple(
                dog.model_copy(
                    update={"name": names[index], "housing_code": f"A1-0{index + 1}"}
                )
                if index < 4
                else dog
                for index, dog in enumerate(frozen.dogs)
            )
        }
    )
    text = "Dog " + "; dog ".join(str(dog.id) for dog in frozen.dogs[:4])
    text += ". e-001 and validate_day are literal dog names. No extra dogs."
    result = display(frozen).explanation(text)
    assert result.status == "ready"
    dog_parts = [part for part in result.segments if part.entity is not None]
    assert [part.text for part in dog_parts] == [
        "e-001",
        "validate_day · A1-02 · standard",
        "validate_day · A1-03 · standard",
        "<e-999>",
    ]
    assert [part.entity.id for part in dog_parts] == [
        str(dog.id) for dog in frozen.dogs[:4]
    ]
    assert "e-001 and validate_day are literal dog names. No extra dogs." in flattened(
        result
    )
    assert all(part.path and part.path.startswith("/demo/dogs/") for part in dog_parts)
    # HTML and model URLs remain inert plain text; they create no links.
    html = '<img src="https://elsewhere.invalid/a"> No 5 km session was recorded.'
    literal = display(frozen).explanation(html)
    assert flattened(literal) == html and all(
        part.path is None for part in literal.segments
    )


def test_presentation_expansion_stays_bounded_without_changing_raw_explanation() -> (
    None
):
    frozen = state()
    ref = references_for(frozen, "PLAN_PRESENCE")[0]
    # A 4,000-character answer may grow through readable labels; DTO chunks stay
    # bounded, and the original text/facts are never shortened or rewritten.
    text = (ref.evidence_id + " ") * 500
    result = display(frozen).explanation(text, references=(ref,))
    assert result.status == "ready"
    assert flattened(result) == "saved-plan record " * 500
    assert all(len(part.text) <= 4000 for part in result.segments)
    assert len(result.segments) <= 256
    assert text == (ref.evidence_id + " ") * 500
