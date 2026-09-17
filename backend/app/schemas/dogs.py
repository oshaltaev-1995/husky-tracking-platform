from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class DogSort(StrEnum):
    NAME = "name"
    YOUNGEST = "youngest"
    OLDEST = "oldest"
    HOUSING = "housing"
    CLASS = "class"


class ArchiveSort(StrEnum):
    NAME = "name"
    ARCHIVE_DATE_DESC = "archive_date_desc"
    ARCHIVE_DATE_ASC = "archive_date_asc"
    YOUNGEST = "youngest"
    OLDEST = "oldest"


class LocationRead(BaseModel):
    code: str
    display_name: str
    location_type: str
    zone: str
    row: str


class ArchiveRead(BaseModel):
    archive_date: date
    reason: str
    note: str | None


class CurrentDogStateRead(BaseModel):
    reference_date: date
    lifecycle: str
    dog_class: str | None
    class_is_historical: bool
    availability: str | None
    housing: LocationRead | None


class DogListItemRead(BaseModel):
    id: UUID
    name: str
    birth_date: date
    age_years: int
    age_months: int
    age_label: str
    sex: str
    is_neutered: bool
    litter_code: str | None
    capabilities: list[str]
    state: CurrentDogStateRead
    photo_key: str | None


class ActivePopulationSummaryRead(BaseModel):
    total: int
    puppy: int
    junior: int
    training: int
    standard: int


class DogsRegistryRead(BaseModel):
    reference_date: date
    result_count: int
    summary: ActivePopulationSummaryRead
    housing_groups: list[str]
    items: list[DogListItemRead]


class ArchiveListItemRead(BaseModel):
    id: UUID
    name: str
    birth_date: date
    age_years: int
    age_months: int
    age_label: str
    sex: str
    litter_code: str | None
    archive: ArchiveRead
    offspring_count: int
    photo_key: str | None


class ArchiveRegistryRead(BaseModel):
    reference_date: date
    result_count: int
    total_archived: int
    items: list[ArchiveListItemRead]


class DogProfileRead(BaseModel):
    id: UUID
    name: str
    birth_date: date
    age_years: int
    age_months: int
    age_label: str
    sex: str
    is_neutered: bool
    neutered_on: date | None
    photo_key: str | None
    notes: str | None
    litter_code: str | None
    litter_birth_date: date | None
    capabilities: list[str]
    state: CurrentDogStateRead
    archive: ArchiveRead | None
    last_known_housing: LocationRead | None


class RelatedDogRead(BaseModel):
    id: UUID
    name: str
    birth_date: date
    lifecycle: str
    dog_class: str | None


class GrandparentPairRead(BaseModel):
    mother: RelatedDogRead | None
    father: RelatedDogRead | None


class LitterPedigreeRead(BaseModel):
    code: str
    birth_date: date
    siblings: list[RelatedDogRead]


class OffspringLitterRead(BaseModel):
    code: str
    birth_date: date
    children: list[RelatedDogRead]


class DogPedigreeRead(BaseModel):
    dog_id: UUID
    mother: RelatedDogRead | None
    father: RelatedDogRead | None
    maternal_grandparents: GrandparentPairRead
    paternal_grandparents: GrandparentPairRead
    litter: LitterPedigreeRead | None
    offspring: list[OffspringLitterRead]


class DogWorkSummaryRead(BaseModel):
    total_km: int
    starts: int
    starts_5km: int
    starts_10km: int
    last_work_date: date | None
    average_km_per_start: float | None


class DogWorkEntryRead(BaseModel):
    date: date
    distance_km: int
    activity_type: str
    label: str | None
    role: str | None


class DogWeeklyWorkRead(BaseModel):
    week_start: date
    starts: int
    total_km: int


class DogWorkRead(BaseModel):
    dog_id: UUID
    season_start: date
    season_end: date
    summary: DogWorkSummaryRead
    weekly: list[DogWeeklyWorkRead]
    entries: list[DogWorkEntryRead]


class PeriodHistoryRead(BaseModel):
    value: str
    valid_from: date
    valid_to: date | None
    is_current: bool
    note: str | None = None


class HousingHistoryRead(BaseModel):
    location: LocationRead
    valid_from: date
    valid_to: date | None
    is_current: bool
    note: str | None


class DogHistoryRead(BaseModel):
    dog_id: UUID
    reference_date: date
    availability: list[PeriodHistoryRead]
    classes: list[PeriodHistoryRead]
    lifecycle: list[PeriodHistoryRead]
    housing: list[HousingHistoryRead]
    archive: ArchiveRead | None
