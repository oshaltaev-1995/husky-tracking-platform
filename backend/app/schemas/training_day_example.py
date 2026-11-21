from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.daily_plans import PlanParticipantRead


class TrainingDayParticipantRead(PlanParticipantRead):
    capabilities: list[str]


class TrainingDayWindowRead(BaseModel):
    sequence: int
    start_time: time
    suggested_end_time: time
    title: str
    distance_km: Literal[5] = 5


class TrainingDayProposal(BaseModel):
    date: date
    preset_version: Literal["training-day-v1"] = "training-day-v1"
    available: bool
    unavailable_reason: str | None
    activities: list[TrainingDayWindowRead]
    participants: list[TrainingDayParticipantRead]
    unique_dogs: int
    planned_participations: int
    planned_dog_km: int
    planned_km_per_dog: int
    precondition: str | None


class TrainingDayApply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    preset_version: Literal["training-day-v1"]
    participant_ids: list[UUID] = Field(min_length=16, max_length=16)
    precondition: str = Field(min_length=67, max_length=67)

    @field_validator("participant_ids")
    @classmethod
    def unique_participants(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Choose sixteen distinct dogs")
        return value
