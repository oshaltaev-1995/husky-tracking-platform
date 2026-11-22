from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["lead", "team", "wheel"]
ToolName = Literal[
    "get_day_plan",
    "get_saved_teams",
    "get_dog_states",
    "get_workload",
    "get_housing",
    "validate_day",
]
Status = Literal["pass", "violation", "attention", "unverified"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class OperationError(Exception):
    """Only a typed, safe code leaves the boundary; never echo input/ORM errors."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Entity(Frozen):
    kind: Literal["day", "dog", "activity", "actual", "location"]
    id: str = Field(min_length=1, max_length=80)


class Value(Frozen):
    name: str = Field(min_length=1, max_length=64)
    value: int | str | bool | None
    unit: Literal["km", "count", "days", "state", "date"]


class Evidence(Frozen):
    id: str
    selected_date: date
    entities: tuple[Entity, ...]
    values: tuple[Value, ...]


class Check(Frozen):
    rule: str
    status: Status
    explanation: str
    selected_date: date
    entities: tuple[Entity, ...]
    evidence_ids: tuple[str, ...]


class Eligibility(Frozen):
    dog_id: UUID
    reasons: tuple[str, ...]


class SavedSlot(Frozen):
    dog_id: UUID
    pair_index: int
    side: str
    role: str
    order: int


class SavedTeam(Frozen):
    sequence: int
    size: int
    slots: tuple[SavedSlot, ...] = Field(max_length=12)


class Activity(Frozen):
    id: UUID
    sequence: int
    kind: str
    distance_km: int | None
    participants: tuple[UUID, ...] = Field(max_length=60)
    eligibility: tuple[Eligibility, ...] = Field(max_length=60)
    teams: tuple[SavedTeam, ...] = Field(max_length=6)
    lineup_error: str | None = None
    actual_status: str


class DogState(Frozen):
    id: UUID
    name: str = Field(max_length=120)
    born: bool
    lifecycle: str | None
    dog_class: str | None
    availability: str | None
    capabilities: tuple[Role, ...]
    housing_code: str | None
    housing_source: Literal["canonical", "workspace_override", "unhoused"]
    km_7d_before: int
    km_14d_before: int
    season_km_before: int
    starts_14d_before: int
    days_since_work_before: int | None
    actual_km_on_date: int
    starts_on_date: int


class Actual(Frozen):
    id: UUID
    distance_km: int
    participants: tuple[UUID, ...] = Field(max_length=60)


class Location(Frozen):
    code: str
    nominal_capacity: int
    residents: tuple[UUID, ...] = Field(max_length=60)


class Snapshot(Frozen):
    contract: Literal["operations-snapshot-v1"] = "operations-snapshot-v1"
    id: UUID
    captured_at: datetime
    selected_date: date
    plan_exists: bool
    plan_revision: int | None
    activities: tuple[Activity, ...] = Field(max_length=32)
    dogs: tuple[DogState, ...] = Field(max_length=60)
    actual: tuple[Actual, ...] = Field(max_length=64)
    locations: tuple[Location, ...] = Field(max_length=32)
    evidence: tuple[Evidence, ...] = Field(max_length=512)
    checks: tuple[Check, ...] = Field(max_length=512)


class ToolArguments(Frozen):
    """Internal normalized selection; each published tool has its own contract."""

    selected_date: date
    dog_ids: tuple[UUID, ...] = Field(default=(), max_length=60)
    activity_ids: tuple[UUID, ...] = Field(default=(), max_length=32)


class DayArguments(Frozen):
    selected_date: date


class ActivityArguments(DayArguments):
    activity_ids: tuple[UUID, ...] = Field(default=(), max_length=32)


class SelectedDogArguments(DayArguments):
    dog_ids: tuple[UUID, ...] = Field(min_length=1, max_length=60)


class HousingArguments(DayArguments):
    dog_ids: tuple[UUID, ...] = Field(default=(), max_length=60)


class ToolResult(Frozen):
    snapshot_id: UUID
    selected_date: date
    tool: ToolName
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=512)
    # A canonical JSON string prevents mutable nested dict/list aliases.
    data_json: str = Field(max_length=96_000)


class ClaimReference(Frozen):
    snapshot_id: UUID
    selected_date: date
    evidence_id: str
    entity: Entity


class ReferencedExplanation(Frozen):
    """References are checked; free explanation is untrusted, not truth-certified."""

    explanation: str = Field(max_length=4000)
    references: tuple[ClaimReference, ...] = Field(min_length=1, max_length=32)
