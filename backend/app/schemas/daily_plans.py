from __future__ import annotations

from datetime import date, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import PlannedActivityType


class MoveDirection(StrEnum):
    UP = "up"
    DOWN = "down"


class PlanParticipantRead(BaseModel):
    id: UUID
    name: str
    housing_code: str | None
    dog_class: str | None
    availability: str | None


class PlannedActivityRead(BaseModel):
    id: UUID
    activity_type: PlannedActivityType
    sequence: int
    start_time: time | None
    title: str
    distance_km: int | None
    notes: str | None
    participants: list[PlanParticipantRead]


class DailyPlanRead(BaseModel):
    selected_date: date
    season_start: date
    season_end: date
    reference_date: date
    exists: bool
    id: UUID | None
    revision: int | None
    notes: str | None
    activities: list[PlannedActivityRead]


class PlanNoteUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class ActivityWrite(BaseModel):
    activity_type: PlannedActivityType
    start_time: time | None = None
    title: str = Field(min_length=1, max_length=120)
    distance_km: int | None = None
    notes: str | None = Field(default=None, max_length=1000)
    participant_ids: list[UUID] = Field(min_length=1, max_length=60)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title is required")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_activity_notes(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def validate_distance_and_participants(self) -> ActivityWrite:
        if len(self.participant_ids) != len(set(self.participant_ids)):
            raise ValueError("the same dog cannot appear twice in one activity")
        if self.activity_type is PlannedActivityType.TRAINING:
            if self.distance_km not in {5, 10}:
                raise ValueError("Training distance must be 5 km or 10 km")
        elif self.distance_km is not None:
            raise ValueError("only Training activities have sled distance")
        return self


class ActivityMove(BaseModel):
    direction: MoveDirection
    expected_revision: int = Field(ge=1)


class EligibleDogRead(BaseModel):
    id: UUID
    name: str
    housing_code: str | None
    dog_class: str | None
    availability: str | None
    eligible: bool
    reasons: list[str]
    planned_training_km: int


class EligibilityRead(BaseModel):
    selected_date: date
    activity_type: PlannedActivityType
    distance_km: int | None
    max_daily_training_km: int
    dogs: list[EligibleDogRead]
