"""Run-bound observations selected by AI and worded only by the application.

This is a finite presentation catalog over the already issued validate_day result,
not another rule engine. It owns no Session, network transport or mutable domain
state. Model output can select opaque IDs only; it never supplies displayed prose,
values, identity, evidence or URLs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationError

from app.operations.api_schemas import (
    ReviewDisplay,
    ReviewDisplaySegment,
    ReviewObservation,
)
from app.operations.display import FrozenDisplay
from app.operations.provider_models import json_object
from app.operations.schemas import (
    ClaimReference,
    Entity,
    Frozen,
    OperationError,
    ReferencedExplanation,
    Snapshot,
    ToolResult,
)
from app.operations.tools import FrozenTools, _validation_result

MAX_OBSERVATIONS = 32
MAX_SELECTION = 6
MAX_CATALOG_BYTES = 12_288
Scope = Literal[
    "day",
    "plan_activity",
    "plan_participants",
    "actual",
    "housing",
    "other_snapshot_dogs",
]


class ObservationSelection(Frozen):
    observation_ids: tuple[str, ...] = Field(min_length=1, max_length=MAX_SELECTION)


class RenderedSelection(Frozen):
    answer: ReferencedExplanation
    presentation: ReviewDisplay


@dataclass(frozen=True, slots=True)
class _Observation:
    id: str
    kind: str
    scope: Scope
    values_json: str
    meaning: str
    references: tuple[ClaimReference, ...]
    segments: tuple[ReviewDisplaySegment, ...]


_ACTUAL = {
    "not_recorded": "Actual work has not been recorded. Whether the activity took "
    "place is not established by the saved data.",
    "not_run": "The activity is marked as not run.",
    "matches_plan": "Recorded work matches the saved plan.",
    "modified": "Recorded work differs from the saved plan.",
    "context_only": "This is a context-only activity; it is not a Training "
    "actual-work confirmation.",
}
_AVAILABILITY = {
    "available": "Available",
    "injured": "Injured",
    "rest": "Rest",
    "restricted": "Restricted",
    "retired": "Retired",
}
_RULE = {
    "ACTIVITY_DISTANCE": "Activity distance",
    "PARTICIPANT_ELIGIBILITY": "Participant eligibility",
    "SAVED_LINEUP": "Saved teams",
    "ACTUAL_RECORDING": "Actual recording",
    "PLANNED_DAILY_KM": "Planned workload",
    "ACTUAL_DAILY_KM": "Recorded workload",
    "DATED_STATE_MISSING": "Dated information",
    "DOG_STATE": "Dated dog state",
    "WORKLOAD_BEFORE": "Previous recorded work",
    "HOUSING_INFORMATION": "Housing information",
    "PLAN_PRESENCE": "Saved plan",
    "ACTUAL_LEDGER": "Recorded work",
}
_STATUS = {
    "violation": "an issue",
    "attention": "attention",
    "unverified": "unverified detail",
}


def _encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OperationError("invalid_evidence")
    return value


def _rows(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise OperationError("invalid_evidence")
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise OperationError("invalid_evidence")
    return value


class ObservationCatalog:
    """One opaque catalog, bound to run + snapshot + exact bounded tool result.

    Construction verifies every admitted detail against its frozen source. Hidden
    detail is used only to reject mismatches, never to create extra observations.
    Rendering names is the same explicit identity lookup as the existing summary.
    """

    def __init__(
        self,
        snapshot: Snapshot,
        result: ToolResult,
        run_id: str,
        link: Callable[[Entity], str],
    ) -> None:
        if (
            result.tool != "validate_day"
            or result.snapshot_id != snapshot.id
            or result.selected_date != snapshot.selected_date
            or not run_id
            or len(run_id) > 100
            or len(result.model_dump_json().encode()) > 16_384
        ):
            raise OperationError("invalid_evidence")
        self._snapshot = snapshot
        self._result = result
        self._link = link
        self._display = FrozenDisplay(snapshot, link)
        self._canonical_link = FrozenTools(snapshot).link
        self._binding = hashlib.sha256(
            (
                run_id + "\0" + str(snapshot.id) + "\0" + result.model_dump_json()
            ).encode()
        ).hexdigest()
        self._dogs = {str(row.id): row for row in snapshot.dogs}
        self._observations: tuple[_Observation, ...] = ()
        self._omitted_candidates = 0
        try:
            data = json_object(result.data_json)
            self._verify_issued_result()
            self._build(data)
        except (ValueError, TypeError, KeyError, ValidationError):
            raise OperationError("invalid_evidence") from None
        while (
            self._observations
            and len(self.provider_json().encode()) > MAX_CATALOG_BYTES
        ):
            self._observations = self._observations[:-1]
            self._omitted_candidates += 1
        if not self._observations:
            raise OperationError("invalid_evidence")

    def _verify_issued_result(self) -> None:
        # Reuse the existing pure bounded formatter as the applicability/evidence
        # contract. This is not another registered tool execution or database read.
        # The candidate builder below still reads ONLY the supplied issued data;
        # this equality check cannot expose omitted details to it or the provider.
        if self._result != _validation_result(self._snapshot):
            raise OperationError("invalid_evidence")
        self._issued = {
            row.id: row
            for row in self._snapshot.evidence
            if row.id in self._result.evidence_ids
        }

    def _check_ids(self, ids: object, entity: Entity) -> tuple[ClaimReference, ...]:
        if (
            not isinstance(ids, (list, tuple))
            or any(not isinstance(identity, str) for identity in ids)
            or len(set(ids)) != len(ids)
        ):
            raise OperationError("invalid_evidence")
        result = []
        for identity in ids:
            row = self._issued.get(identity)
            if (
                row is None
                or row.selected_date != self._snapshot.selected_date
                or entity not in row.entities
            ):
                raise OperationError("invalid_evidence")
            result.append(
                ClaimReference(
                    snapshot_id=self._snapshot.id,
                    selected_date=self._snapshot.selected_date,
                    evidence_id=identity,
                    entity=entity,
                )
            )
        return tuple(result)

    def _refs(
        self, ids: object, entity: Entity, rule: str | None = None
    ) -> tuple[ClaimReference, ...]:
        rows = self._check_ids(ids, entity)
        if rule is None:
            return rows
        eligible = {
            identity
            for check in self._snapshot.checks
            if check.rule == rule and entity in check.entities
            for identity in check.evidence_ids
        }
        return tuple(ref for ref in rows if ref.evidence_id in eligible)

    def _segment(self, text: str, entity: Entity | None = None) -> ReviewDisplaySegment:
        path = self._link(entity) if entity is not None else None
        if path is not None:
            parsed = urlsplit(path)
            if (
                parsed.scheme
                or parsed.netloc
                or not parsed.path.startswith("/demo/")
                or parsed.fragment
                or "\\" in path
                or "%" in path
                or any(ord(c) <= 32 for c in path)
                or entity is not None
                and path != self._canonical_link(entity)
            ):
                raise OperationError("invalid_evidence")
            if (
                entity is not None
                and entity.kind == "dog"
                and parsed.path != "/demo/dogs/" + entity.id
            ):
                raise OperationError("invalid_evidence")
        return ReviewDisplaySegment(text=text, entity=entity, path=path)

    def _identity(
        self,
        kind: str,
        scope: Scope,
        values_json: str,
        meaning: str,
        references: tuple[ClaimReference, ...],
        segments: tuple[ReviewDisplaySegment, ...],
    ) -> str:
        payload = _encoded(
            {
                "binding": self._binding,
                "kind": kind,
                "scope": scope,
                "values": values_json,
                "meaning": meaning,
                "references": [r.model_dump(mode="json") for r in references],
                "segments": [s.model_dump(mode="json") for s in segments],
            }
        )
        return "o-" + hashlib.sha256(payload.encode()).hexdigest()[:24]

    def _add(
        self,
        kind: str,
        scope: Scope,
        values: object,
        meaning: str,
        references: tuple[ClaimReference, ...],
        segments: tuple[ReviewDisplaySegment, ...],
    ) -> None:
        if not references:
            return
        refs = tuple(dict.fromkeys(references))
        values_json = _encoded(values)
        identity = self._identity(kind, scope, values_json, meaning, refs, segments)
        observation = _Observation(
            identity, kind, scope, values_json, meaning, refs, segments
        )
        if any(row.id == identity for row in self._observations):
            return
        if len(self._observations) >= MAX_OBSERVATIONS:
            self._omitted_candidates += 1
            return
        previous = self._observations
        self._observations += (observation,)
        if len(self.provider_json().encode()) > MAX_CATALOG_BYTES:
            self._observations = previous
            self._omitted_candidates += 1

    def _build(self, data: dict[str, Any]) -> None:
        plan = _object(data["plan"])
        actual = _object(data["actual"])
        day = Entity(kind="day", id=str(self._snapshot.selected_date))
        dayrefs = self._refs(plan["evidence_ids"], day, "PLAN_PRESENCE")
        actualrefs = self._refs(actual["evidence_ids"], day, "ACTUAL_LEDGER")
        count = _count(plan["activity_count"])
        plan_text = (
            "No saved plan exists for this date."
            if not plan["exists"]
            else "The saved plan has no activities."
            if count == 0
            else f"The saved plan contains {count} "
            + ("activity." if count == 1 else "activities.")
        )
        self._add(
            "plan_presence",
            "day",
            {"plan_exists": plan["exists"], "activity_count": count},
            plan_text,
            dayrefs,
            (self._segment(plan_text),),
        )
        metric_text = ", ".join(
            f"{actual[key]} {label}"
            if actual[key] is not None
            else label + " not verified"
            for key, label in (
                ("sessions", "recorded sessions"),
                ("dog_starts", "recorded dog starts"),
                ("dog_km", "recorded dog-km"),
            )
        )
        actual_text = (
            "Recorded work: "
            + metric_text
            + ". These recorded totals do not establish whether "
            "unrecorded activity took place."
        )
        self._add(
            "actual_totals",
            "actual",
            {key: actual[key] for key in ("sessions", "dog_starts", "dog_km")},
            actual_text,
            actualrefs,
            (self._segment(actual_text),),
        )
        for raw in _rows(plan["activities"]):
            row = _object(raw)
            entity = Entity(kind="activity", id=row["id"])
            label = self._display.activity_label(row["id"])
            if label is None:
                raise OperationError("invalid_evidence")
            prefix = self._segment(label, entity)
            status = row["actual_status"]
            if status not in _ACTUAL:
                raise OperationError("invalid_evidence")
            self._add(
                "actual_status",
                "plan_activity",
                {
                    "kind": row["kind"],
                    "distance_km": row["distance_km"],
                    "actual_status": status,
                },
                _ACTUAL[status],
                self._refs(row["evidence_ids"], entity, "ACTUAL_RECORDING"),
                (prefix, self._segment(": " + _ACTUAL[status])),
            )
            pool = _count(row["selected_pool_count"])
            text = (
                f"The selected pool contains {pool} "
                + ("dog" if pool == 1 else "dogs")
                + "; a selected pool is distinct from saved teams."
                if row["kind"] == "training"
                else f"{pool} "
                + ("dog selected" if pool == 1 else "dogs selected")
                + " for this planned activity."
            )
            self._add(
                "selected_pool",
                "plan_participants",
                {
                    "kind": row["kind"],
                    "distance_km": row["distance_km"],
                    "selected_pool_count": pool,
                },
                text,
                self._refs(row["evidence_ids"], entity, "PARTICIPANT_ELIGIBILITY"),
                (prefix, self._segment(": " + text)),
            )
            if row["kind"] == "training":
                teams = _count(row["saved_teams"])
                text = (
                    "No teams are saved for this Training activity; "
                    "the selected pool remains separate."
                    if teams == 0
                    else f"{teams} "
                    + ("team is" if teams == 1 else "teams are")
                    + " saved. Team planning does not confirm Actual work."
                )
                self._add(
                    "saved_teams",
                    "plan_activity",
                    {"saved_teams": teams},
                    text,
                    self._refs(row["evidence_ids"], entity, "SAVED_LINEUP"),
                    (prefix, self._segment(": " + text)),
                )
            eligible = _count(row["eligible_count"])
            invalid = _count(row["ineligible_count"])
            unknown = _count(row["eligibility_unverified_count"])
            text = (
                f"Dated eligibility checks report {eligible} eligible, "
                f"{invalid} ineligible and {unknown} unverified selected participants. "
                "This is not a medical or training-safety assessment."
            )
            self._add(
                "eligibility",
                "plan_participants",
                {"eligible": eligible, "ineligible": invalid, "unverified": unknown},
                text,
                self._refs(row["evidence_ids"], entity, "PARTICIPANT_ELIGIBILITY"),
                (prefix, self._segment(": " + text)),
            )
        for raw in _rows(data["selected_dog_states"]):
            row = _object(raw)
            entity = Entity(kind="dog", id=row["id"])
            dog = self._dogs[row["id"]]
            state = _AVAILABILITY.get(row["availability"], "not verified")
            lifecycle = {"active": "Active", "archived": "Archived"}.get(
                row["lifecycle"], "not verified"
            )
            text = (
                f"Dated availability: {state}; lifecycle: {lifecycle}. "
                "These states are separate from activity eligibility "
                "and training safety."
            )
            self._add(
                "selected_dog_state",
                "plan_participants",
                {
                    "born": row["born"],
                    "availability": row["availability"],
                    "lifecycle": row["lifecycle"],
                },
                text,
                self._refs(row["evidence_ids"], entity, "DOG_STATE"),
                (self._segment(dog.name, entity), self._segment(": " + text)),
            )
        for raw in _rows(data["checks"]):
            row = _object(raw)
            finding_label = _RULE.get(row["rule"])
            if (
                finding_label is None
                or row["status"] not in _STATUS
                or row["rule"] in {"ACTUAL_RECORDING", "SAVED_LINEUP"}
            ):
                continue
            entities = tuple(Entity.model_validate(x) for x in row["entities"])
            refs = tuple(
                ref
                for entity in entities
                for ref in self._refs(row["evidence_ids"], entity, row["rule"])
            )
            scope: Scope = row["scope"]
            qualifier = (
                "Outside the selected and Actual pools: "
                if scope == "other_snapshot_dogs"
                else ""
            )
            text = (
                qualifier
                + finding_label
                + ": the existing check reports "
                + _STATUS[row["status"]]
                + ". Full checked findings remain available below."
            )
            self._add(
                "finding",
                scope,
                {"rule": row["rule"], "status": row["status"]},
                text,
                refs,
                (self._segment(text),),
            )
        omitted = (
            _count(data["omitted_detail_count"])
            + _count(data["omitted_selected_dog_state_count"])
            + _count(plan["omitted_activity_count"])
        )
        unverified = _count(data["status_counts"].get("unverified", 0))
        if omitted or unverified:
            text = (
                "Some saved-snapshot detail is omitted or not verified. "
                "This selection is not an exhaustive review "
                "or a training-safety assessment."
            )
            self._add(
                "qualification",
                "day",
                {"omitted_details": omitted, "unverified_checks": unverified},
                text,
                dayrefs or actualrefs,
                (self._segment(text),),
            )

    def provider_json(self) -> str:
        return _encoded(
            {
                "snapshot_id": str(self._snapshot.id),
                "selected_date": str(self._snapshot.selected_date),
                "observations": [
                    {
                        "id": row.id,
                        "type": row.kind,
                        "scope": row.scope,
                        "values": json.loads(row.values_json),
                        "meaning": row.meaning,
                    }
                    for row in self._observations
                ],
                "omitted_observation_count": self._omitted_candidates,
            }
        )

    def select(self, selection_json: str) -> RenderedSelection:
        try:
            if len(selection_json.encode()) > 16_384:
                raise ValueError
            json_object(selection_json)
            selection = ObservationSelection.model_validate_json(selection_json)
            if len(set(selection.observation_ids)) != len(selection.observation_ids):
                raise ValueError
        except (ValueError, TypeError, ValidationError):
            raise OperationError("invalid_selection") from None
        lookup = {row.id: row for row in self._observations}
        segments: list[ReviewDisplaySegment] = []
        observations: list[ReviewObservation] = []
        refs: list[ClaimReference] = []
        for identity in selection.observation_ids:
            row = lookup.get(identity)
            if row is None or row.id != self._identity(
                row.kind,
                row.scope,
                row.values_json,
                row.meaning,
                row.references,
                row.segments,
            ):
                raise OperationError("invalid_evidence")
            for ref in row.references:
                if (
                    ref.snapshot_id != self._snapshot.id
                    or ref.selected_date != self._snapshot.selected_date
                ):
                    raise OperationError("invalid_evidence")
                evidence = self._issued.get(ref.evidence_id)
                if evidence is None or ref.entity not in evidence.entities:
                    raise OperationError("invalid_evidence")
            if segments:
                segments.append(self._segment(" "))
            segments.extend(row.segments)
            observations.append(ReviewObservation(segments=row.segments))
            refs.extend(row.references)
        unique_refs = tuple(dict.fromkeys(refs))
        if len(unique_refs) > 32:
            raise OperationError("invalid_evidence")
        explanation = "".join(row.text for row in segments)
        try:
            answer = ReferencedExplanation(
                explanation=explanation, references=unique_refs
            )
            presentation = ReviewDisplay(
                status="ready",
                segments=tuple(segments),
                observations=tuple(observations),
                message=None,
            )
            return RenderedSelection(answer=answer, presentation=presentation)
        except ValidationError:
            raise OperationError("invalid_evidence") from None
