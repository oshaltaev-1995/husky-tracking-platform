from __future__ import annotations

import json
from collections import Counter
from typing import Any
from urllib.parse import urlencode

from pydantic import ValidationError

from app.operations.provider_models import json_object
from app.operations.schemas import (
    ActivityArguments,
    Check,
    DayArguments,
    Entity,
    Frozen,
    HousingArguments,
    OperationError,
    ReferencedExplanation,
    SelectedDogArguments,
    Snapshot,
    ToolArguments,
    ToolName,
    ToolResult,
)

READ_TOOLS: tuple[ToolName, ...] = (
    "get_day_plan",
    "get_saved_teams",
    "get_dog_states",
    "get_workload",
    "get_housing",
    "validate_day",
)

# The provider policy already enforces this whole-result limit. Compact this one
# mandatory projection within it instead of raising the existing provider budget.
VALIDATION_RESULT_BYTES = 16_384


def _validation_result(snapshot: Snapshot) -> ToolResult:
    """Keep successful plan facts beside scoped findings in one bounded read.

    Counts cover the whole detached snapshot. Detail is admitted together with its
    issued evidence, so omission never changes a selected pool into an empty one.
    Eligibility/lineup results come from capture/checks, not an alternative rule.
    """
    selected_ids = {
        dog_id for activity in snapshot.activities for dog_id in activity.participants
    }
    selected_strings = {str(item) for item in selected_ids}
    evidence = {row.id: row.model_dump(mode="json") for row in snapshot.evidence}

    def evidence_for(rule: str, kind: str, entity_id: str) -> list[str]:
        return list(
            dict.fromkeys(
                evidence_id
                for check in snapshot.checks
                if check.rule == rule
                and any(
                    entity.kind == kind and entity.id == entity_id
                    for entity in check.entities
                )
                for evidence_id in check.evidence_ids
            )
        )

    def scope(check: Check) -> str:
        if check.rule.startswith("ACTUAL_") or any(
            entity.kind == "actual" for entity in check.entities
        ):
            return "actual"
        if any(
            entity.kind == "dog" and entity.id in selected_strings
            for entity in check.entities
        ):
            return "plan_participants"
        if any(entity.kind == "activity" for entity in check.entities):
            return "plan_activity"
        if any(entity.kind == "dog" for entity in check.entities):
            return "other_snapshot_dogs"
        if any(entity.kind == "location" for entity in check.entities):
            return "housing"
        return "day"

    day = snapshot.selected_date.isoformat()
    plan_evidence = evidence_for("PLAN_PRESENCE", "day", day)
    actual_evidence = evidence_for("ACTUAL_LEDGER", "day", day)
    actual_values = {
        item.name: item.value
        for row in snapshot.evidence
        if row.id in actual_evidence
        for item in row.values
    }
    findings = [check for check in snapshot.checks if check.status != "pass"]
    by_scope = Counter(scope(check) for check in findings)
    result: dict[str, Any] = {
        "plan": {
            "exists": snapshot.plan_exists,
            "activity_count": len(snapshot.activities),
            "selected_unique_dogs": len(selected_ids),
            "selected_participations": sum(
                len(activity.participants) for activity in snapshot.activities
            ),
            "evidence_ids": plan_evidence,
            "activities": [],
            "omitted_activity_count": len(snapshot.activities),
        },
        "selected_dog_states": [],
        "omitted_selected_dog_state_count": len(selected_ids),
        "actual": {
            "sessions": actual_values.get("sessions"),
            "dog_starts": actual_values.get("dog_starts"),
            "dog_km": actual_values.get("dog_km"),
            "unique_dogs": len(
                {dog_id for row in snapshot.actual for dog_id in row.participants}
            ),
            "evidence_ids": actual_evidence,
        },
        "checked_rules": sorted({row.rule for row in snapshot.checks}),
        "status_counts": dict(Counter(row.status for row in snapshot.checks)),
        "finding_counts_by_scope": dict(sorted(by_scope.items())),
        "checks": [],
        "omitted_detail_count": len(findings),
        "evidence": [],
        "qualification": "Counts cover the full frozen snapshot; omitted detail "
        "is unknown, not zero. Selected pools, saved teams and actual work are "
        "independent. Other snapshot dogs are not plan participants. Only these "
        "checks, not a guarantee of training safety; no inference that a plan ran.",
    }
    issued_ids = set(plan_evidence + actual_evidence)

    def serialize() -> ToolResult:
        result["evidence"] = [
            evidence[row.id] for row in snapshot.evidence if row.id in issued_ids
        ]
        return ToolResult(
            snapshot_id=snapshot.id,
            selected_date=snapshot.selected_date,
            tool="validate_day",
            evidence_ids=tuple(
                row.id for row in snapshot.evidence if row.id in issued_ids
            ),
            data_json=json.dumps(result, sort_keys=True, separators=(",", ":")),
        )

    def admit(rows: list[Any], row: dict[str, Any], ids: list[str]) -> bool:
        previous_ids = issued_ids.copy()
        rows.append(row)
        issued_ids.update(ids)
        if len(serialize().model_dump_json().encode()) <= VALIDATION_RESULT_BYTES:
            return True
        rows.pop()
        issued_ids.clear()
        issued_ids.update(previous_ids)
        return False

    # Invalid selected dogs must not lose priority to unrelated archived states.
    activities = sorted(
        snapshot.activities,
        key=lambda activity: not any(item.reasons for item in activity.eligibility),
    )
    for activity in activities:
        eligibility = {item.dog_id: item for item in activity.eligibility}
        invalid = [
            item
            for dog_id in activity.participants
            if (item := eligibility.get(dog_id)) is not None and item.reasons
        ]
        ids = list(
            dict.fromkeys(
                evidence_id
                for rule in (
                    "ACTIVITY_DISTANCE",
                    "PARTICIPANT_ELIGIBILITY",
                    "SAVED_LINEUP",
                    "ACTUAL_RECORDING",
                )
                for evidence_id in evidence_for(rule, "activity", str(activity.id))
            )
        )
        row: dict[str, Any] = {
            "id": str(activity.id),
            "kind": activity.kind,
            "distance_km": activity.distance_km,
            "selected_pool": [str(item) for item in activity.participants],
            "selected_pool_count": len(activity.participants),
            "eligible_count": sum(
                dog_id in eligibility and not eligibility[dog_id].reasons
                for dog_id in activity.participants
            ),
            "ineligible_count": len(invalid),
            "eligibility_unverified_count": sum(
                dog_id not in eligibility for dog_id in activity.participants
            ),
            "ineligible_participants": [
                item.model_dump(mode="json") for item in invalid
            ],
            "saved_teams": len(activity.teams),
            "actual_status": activity.actual_status,
            "evidence_ids": ids,
        }
        if admit(result["plan"]["activities"], row, ids):
            result["plan"]["omitted_activity_count"] -= 1

    invalid_ids = {
        item.dog_id
        for activity in snapshot.activities
        for item in activity.eligibility
        if item.dog_id in activity.participants and item.reasons
    }
    for dog in sorted(snapshot.dogs, key=lambda dog: dog.id not in invalid_ids):
        if dog.id not in selected_ids:
            continue
        ids = evidence_for("DOG_STATE", "dog", str(dog.id))
        row = {
            "id": str(dog.id),
            "born": dog.born,
            "lifecycle": dog.lifecycle,
            "class": dog.dog_class,
            "availability": dog.availability,
            "capabilities": list(dog.capabilities),
            "evidence_ids": ids,
        }
        if admit(result["selected_dog_states"], row, ids):
            result["omitted_selected_dog_state_count"] -= 1

    # Preserve the original 32-detail limit; all canonical checks still contribute
    # status/scope counts even when their detail/evidence will not fit.
    priority = {
        "plan_participants": 0,
        "plan_activity": 1,
        "actual": 2,
        "day": 3,
        "housing": 4,
        "other_snapshot_dogs": 5,
    }
    for check in sorted(findings, key=lambda check: priority[scope(check)]):
        if len(result["checks"]) == 32:
            break
        row = {**check.model_dump(mode="json"), "scope": scope(check)}
        if admit(result["checks"], row, list(check.evidence_ids)):
            result["omitted_detail_count"] -= 1
    return serialize()


ARGUMENTS: dict[ToolName, type[Frozen]] = {
    "get_day_plan": ActivityArguments,
    "get_saved_teams": ActivityArguments,
    "get_dog_states": SelectedDogArguments,
    "get_workload": SelectedDogArguments,
    "get_housing": HousingArguments,
    "validate_day": DayArguments,
}

TOOL_DESCRIPTIONS: dict[ToolName, str] = {
    "get_day_plan": "Read saved plan and participant UUIDs on selected_date. "
    "Use activity_ids only from the current snapshot; omit to read this day.",
    "get_saved_teams": "Read persisted teams and harness slots only. "
    "Use activity UUIDs from get_day_plan and the selected snapshot date.",
    "get_dog_states": "Read dated state/capabilities for one or more dog_ids. "
    "Take dog UUIDs from current plan, teams or housing; selected_date stays fixed.",
    "get_workload": "Read actual workload before selected_date, with today's actual "
    "separate. Nonempty dog UUIDs must come from current snapshot tools.",
    "get_housing": "Read dated housing/provenance; optional snapshot dog_ids. "
    "Omit selection for this day's overview; capacity is informational.",
    "validate_day": "Check the selected snapshot day using canonical rules. "
    "Returns selected pools/eligibility, saved-team and actual facts plus scoped "
    "findings/evidence. Counts cover the day; omitted details are not zero. "
    "No selectors, writes or solver.",
}


class FrozenTools:
    """Closed, detached registry: no Session, network client or write capability."""

    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot

    def contracts(self) -> tuple[tuple[ToolName, str], ...]:
        return tuple(
            (name, json.dumps(ARGUMENTS[name].model_json_schema(), sort_keys=True))
            for name in READ_TOOLS
        )

    def execute(self, name: str, arguments_json: str) -> ToolResult:
        if name not in READ_TOOLS:
            raise OperationError("tool_not_allowed")
        if len(arguments_json.encode()) > 8192:
            raise OperationError("invalid_tool_arguments")
        try:
            raw = json_object(arguments_json)
            if set(raw) - set(ARGUMENTS[name].model_fields):
                raise OperationError("invalid_tool_arguments")
            if name in {"get_dog_states", "get_workload"} and (
                "dog_ids" not in raw or raw["dog_ids"] == []
            ):
                raise OperationError("dog_selection_required")
            selected = ARGUMENTS[name].model_validate_json(arguments_json)
            args = ToolArguments.model_validate_json(selected.model_dump_json())
        except (ValidationError, ValueError, TypeError):
            raise OperationError("invalid_tool_arguments") from None
        snapshot = self.snapshot
        if args.selected_date != snapshot.selected_date:
            raise OperationError("date_not_in_snapshot")
        if len(set(args.dog_ids)) != len(args.dog_ids) or len(
            set(args.activity_ids)
        ) != len(args.activity_ids):
            raise OperationError("invalid_tool_arguments")
        if not set(args.dog_ids) <= {dog.id for dog in snapshot.dogs} or not set(
            args.activity_ids
        ) <= {row.id for row in snapshot.activities}:
            raise OperationError("entity_not_in_snapshot")
        if (
            args.dog_ids
            and name not in {"get_dog_states", "get_workload", "get_housing"}
        ) or (args.activity_ids and name not in {"get_day_plan", "get_saved_teams"}):
            raise OperationError("invalid_tool_arguments")
        if name in {"get_dog_states", "get_workload"} and not args.dog_ids:
            raise OperationError("dog_selection_required")
        data = snapshot.model_dump(mode="json")
        activities = [
            row
            for row in data["activities"]
            if not args.activity_ids
            or row["id"] in {str(item) for item in args.activity_ids}
        ]
        dogs = [
            row
            for row in data["dogs"]
            if not args.dog_ids or row["id"] in {str(item) for item in args.dog_ids}
        ]
        result: object
        if name == "get_day_plan":
            result = {
                "exists": snapshot.plan_exists,
                "revision": snapshot.plan_revision,
                "activities": [
                    {
                        key: value
                        for key, value in row.items()
                        if key not in {"teams", "lineup_error"}
                    }
                    for row in activities
                ],
            }
        elif name == "get_saved_teams":
            result = [
                {
                    "activity_id": row["id"],
                    "selected_pool": row["participants"],
                    "saved_teams": row["teams"],
                    "validator_code": row["lineup_error"],
                }
                for row in activities
            ]
        elif name == "get_dog_states":
            result = [
                {
                    key: value
                    for key, value in row.items()
                    if not key.endswith("_before")
                    and key not in {"actual_km_on_date", "starts_on_date"}
                }
                for row in dogs
            ]
        elif name == "get_workload":
            result = {
                "planning_actual_cutoff": "strictly_before_selected_date",
                "actual_on_selected_date_is_separate": True,
                "dogs": [
                    {
                        key: value
                        for key, value in row.items()
                        if key in {"id", "actual_km_on_date", "starts_on_date"}
                        or key.endswith("_before")
                    }
                    for row in dogs
                ],
            }
        elif name == "get_housing":
            result = {
                "dogs": [
                    {key: row[key] for key in ("id", "housing_code", "housing_source")}
                    for row in dogs
                ],
                "locations": [
                    {
                        "code": row["code"],
                        "nominal_capacity": row["nominal_capacity"],
                        "occupancy": len(row["residents"]),
                        "selected_residents": [
                            resident
                            for resident in row["residents"]
                            if not args.dog_ids
                            or resident in {str(item) for item in args.dog_ids}
                        ],
                    }
                    for row in data["locations"]
                    if not args.dog_ids
                    or any(
                        resident in {str(item) for item in args.dog_ids}
                        for resident in row["residents"]
                    )
                ],
                "nominal_capacity_is_not_a_move_limit": True,
            }
        else:
            return _validation_result(snapshot)
        try:
            related_locations = {
                row.housing_code for row in snapshot.dogs if row.id in args.dog_ids
            }
            return ToolResult(
                snapshot_id=snapshot.id,
                selected_date=snapshot.selected_date,
                tool=name,
                evidence_ids=tuple(
                    row.id
                    for row in snapshot.evidence
                    if not args.dog_ids
                    and not args.activity_ids
                    or any(
                        entity.kind == "dog"
                        and entity.id in {str(item) for item in args.dog_ids}
                        or entity.kind == "activity"
                        and entity.id in {str(item) for item in args.activity_ids}
                        or name == "get_housing"
                        and entity.kind == "location"
                        and entity.id in related_locations
                        for entity in row.entities
                    )
                ),
                data_json=json.dumps(result, sort_keys=True, separators=(",", ":")),
            )
        except ValidationError:
            raise OperationError("tool_result_too_large") from None

    def validate_references(self, answer_json: str) -> ReferencedExplanation:
        if len(answer_json.encode()) > 16_384:
            raise OperationError("invalid_evidence")
        try:
            json_object(answer_json)
            answer = ReferencedExplanation.model_validate_json(answer_json)
        except (ValidationError, ValueError, TypeError):
            raise OperationError("invalid_evidence") from None
        evidence = {row.id: row for row in self.snapshot.evidence}
        for ref in answer.references:
            found = evidence.get(ref.evidence_id)
            if (
                ref.snapshot_id != self.snapshot.id
                or ref.selected_date != self.snapshot.selected_date
                or found is None
                or ref.entity not in found.entities
                or found.selected_date != ref.selected_date
            ):
                raise OperationError("invalid_evidence")
        return answer

    def link(self, entity: Entity) -> str:
        """Only verified snapshot entities receive a trusted local route."""
        when = self.snapshot.selected_date.isoformat()
        query = urlencode({"date": when})
        if entity.kind == "day" and entity.id == when:
            return f"/demo/daily?{query}"
        if entity.kind == "dog" and entity.id in {
            str(dog.id) for dog in self.snapshot.dogs
        }:
            return f"/demo/dogs/{entity.id}?tab=work"
        if entity.kind == "activity":
            activity = next(
                (row for row in self.snapshot.activities if str(row.id) == entity.id),
                None,
            )
            if activity is not None:
                return (
                    f"/demo/daily/{when}/activities/{entity.id}/teams"
                    if activity.kind == "training"
                    else f"/demo/daily?{query}"
                )
        if entity.kind == "actual" and entity.id in {
            str(row.id) for row in self.snapshot.actual
        }:
            return f"/demo/daily-entry?{query}"
        if entity.kind == "location" and entity.id in {
            row.code for row in self.snapshot.locations
        }:
            return f"/demo/kennel?{query}"
        raise OperationError("entity_not_in_snapshot")

    def provider_context(self) -> str:
        """Minimal run envelope. Detail is available only through bounded read tools."""
        return json.dumps(
            {
                "contract": self.snapshot.contract,
                "snapshot_id": str(self.snapshot.id),
                "selected_date": self.snapshot.selected_date.isoformat(),
                "captured_at": self.snapshot.captured_at.isoformat(),
                "plan_exists": self.snapshot.plan_exists,
                "activities": len(self.snapshot.activities),
                "actual_sessions": len(self.snapshot.actual),
                "data_is_untrusted": True,
                "facts_require_server_evidence": True,
            },
            sort_keys=True,
        )
