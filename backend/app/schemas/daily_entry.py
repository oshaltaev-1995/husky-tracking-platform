from __future__ import annotations

from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ActualParticipantWrite(BaseModel):
    dog_id: UUID
    assigned_role: str | None = None
    actual_team_sequence: int | None = Field(default=None, ge=1)
    pair_index: int | None = Field(default=None, ge=0)
    side: str | None = None
    position_order: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_geometry(self) -> ActualParticipantWrite:
        geometry = (
            self.actual_team_sequence,
            self.pair_index,
            self.side,
            self.position_order,
        )
        if any(value is not None for value in geometry):
            if any(value is None for value in geometry) or self.assigned_role is None:
                raise ValueError("positioned participants require complete geometry")
            if self.side not in {"left", "right"}:
                raise ValueError("position side must be left or right")
        elif self.side is not None:
            raise ValueError("unpositioned participants cannot have a side")
        if self.assigned_role not in {None, "lead", "team", "wheel"}:
            raise ValueError("assigned role must be lead, team, or wheel")
        return self


class ActualSessionFields(BaseModel):
    distance_km: int
    start_time: time | None = None
    label: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=255)
    participants: list[ActualParticipantWrite] = Field(min_length=1, max_length=60)

    @field_validator("distance_km")
    @classmethod
    def canonical_distance(cls, value: int) -> int:
        if value not in {5, 10}:
            raise ValueError("actual sled distance must be 5 km or 10 km")
        return value

    @field_validator("label", "note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None

    @model_validator(mode="after")
    def validate_participants(self) -> ActualSessionFields:
        dog_ids = [participant.dog_id for participant in self.participants]
        if len(dog_ids) != len(set(dog_ids)):
            raise ValueError("the same dog cannot appear twice in one actual session")
        positions = [
            (
                participant.actual_team_sequence,
                participant.pair_index,
                participant.side,
            )
            for participant in self.participants
            if participant.actual_team_sequence is not None
        ]
        if len(positions) != len(set(positions)):
            raise ValueError("an actual harness position cannot appear twice")
        return self


class ActualSessionCreate(ActualSessionFields):
    pass


class ActualSessionUpdate(ActualSessionFields):
    expected_revision: int = Field(ge=1)


class ActualParticipantRead(BaseModel):
    dog_id: UUID
    dog_name: str
    housing_code: str | None
    dog_class: str | None
    availability: str | None
    assigned_role: str | None
    actual_team_sequence: int | None
    pair_index: int | None
    pair_label: str | None
    side: str | None
    position_order: int | None


class ActualSessionRead(BaseModel):
    id: UUID
    revision: int
    work_date: date
    start_time: time | None
    distance_km: int
    label: str | None
    note: str | None
    source: str
    planned_activity_id: UUID | None
    planned_activity_title: str | None
    plan_status: str | None
    deviations: list[str]
    team_count: int
    participants: list[ActualParticipantRead]


class PlannedActivityActualRead(BaseModel):
    id: UUID
    activity_type: str
    title: str
    start_time: time | None
    distance_km: int | None
    participant_count: int
    team_count: int
    arranged_dog_count: int
    actual_status: str
    actual_session_id: UUID | None
    deviations: list[str]


class DailyEntrySummaryRead(BaseModel):
    actual_sessions: int
    dogs_worked: int
    dog_starts: int
    total_dog_km: int


class DailyDogRead(BaseModel):
    id: UUID
    name: str
    housing_code: str | None
    dog_class: str | None
    availability: str | None
    starts: int
    actual_km: int


class DailyHousingGroupRead(BaseModel):
    code: str
    display_name: str
    zone: str
    row: str
    position: int
    dogs: list[DailyDogRead]


class DailyEntryRead(BaseModel):
    selected_date: date
    season_start: date
    season_end: date
    reference_date: date
    plan_exists: bool
    planned_activities: list[PlannedActivityActualRead]
    sessions: list[ActualSessionRead]
    summary: DailyEntrySummaryRead
    housing_groups: list[DailyHousingGroupRead]


class ActualEligibleDogRead(BaseModel):
    id: UUID
    name: str
    housing_code: str | None
    dog_class: str | None
    availability: str | None
    capabilities: list[str]
    actual_km_today: int
    eligible: bool
    reasons: list[str]


class ActualEligibilityRead(BaseModel):
    selected_date: date
    distance_km: int
    max_daily_km: int
    dogs: list[ActualEligibleDogRead]
