from __future__ import annotations

import json
from collections import Counter
from urllib.parse import urlencode

from pydantic import ValidationError

from app.operations.provider_models import json_object
from app.operations.schemas import (
    ActivityArguments,
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
    "Returns findings and server evidence; no selectors, writes or solver.",
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
            # Operational attention first; a normal review does not ship every dog's
            # state/history to a model. All facts remain in the frozen local snapshot.
            important = [row for row in data["checks"] if row["status"] != "pass"]
            included = important[:32]
            ids = {item for row in included for item in row["evidence_ids"]}
            result = {
                "checked_rules": sorted(set(row.rule for row in snapshot.checks)),
                "status_counts": dict(Counter(row.status for row in snapshot.checks)),
                "checks": included,
                "omitted_detail_count": max(0, len(important) - len(included)),
                "evidence": [row for row in data["evidence"] if row["id"] in ids],
                "qualification": "Only these checks, not a guarantee of training "
                "safety; no inference that a plan ran.",
            }
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
