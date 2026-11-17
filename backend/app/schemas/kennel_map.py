from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KennelMapResidentRead(BaseModel):
    id: UUID
    name: str
    sex: str
    is_neutered: bool
    dog_class: str | None
    lifecycle: str
    availability: str | None
    housing_code: str
    litter_code: str | None
    photo_key: str | None


class KennelMapLocationRead(BaseModel):
    id: str
    code: str
    display_name: str
    location_type: str
    zone: str
    row: str
    position: int
    capacity: int
    is_active: bool
    residents: list[KennelMapResidentRead]


class KennelMapSummaryRead(BaseModel):
    resident_dogs: int
    occupied_locations: int
    unavailable_dogs: int
    class_counts: dict[str, int]
    sex_counts: dict[str, int]
    neutered_counts: dict[str, int]
    availability_counts: dict[str, int]


class HousingEditRead(BaseModel):
    editable: bool
    effective_date: date
    revision: int | None = None
    precondition: str | None = None
    reason: Literal["workspace_required", "historical_date"] | None = None


class HousingMoveWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dog_id: UUID
    destination_code: str = Field(min_length=1, max_length=30)


class HousingMovesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_date: date
    precondition: str = Field(min_length=1, max_length=128)
    moves: list[HousingMoveWrite] = Field(min_length=1, max_length=60)


class KennelMapSnapshotRead(BaseModel):
    selected_date: date
    season_start: date
    season_end: date
    reference_date: date
    summary: KennelMapSummaryRead
    locations: list[KennelMapLocationRead]
    housing_edit: HousingEditRead
