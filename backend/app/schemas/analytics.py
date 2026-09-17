from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class AnalyticsDogSort(StrEnum):
    HIGHEST_KM = "highest_km"
    LOWEST_KM = "lowest_km"
    MOST_STARTS = "most_starts"
    FEWEST_STARTS = "fewest_starts"
    NAME = "name"


class AnalyticsSummaryRead(BaseModel):
    sessions: int
    dogs_worked: int
    dog_starts: int
    dog_km: int
    average_km_per_worked_dog: float
    average_km_per_start: float
    starts_5km: int
    starts_10km: int
    max_daily_dog_km: int


class WeeklyAnalyticsRead(AnalyticsSummaryRead):
    week_start: date
    week_end: date
    period_start: date
    period_end: date
    iso_week: int


class DistanceBreakdownRead(BaseModel):
    distance_km: int
    dog_starts: int
    dog_km: int


class RoleBreakdownRead(BaseModel):
    role: str
    dog_starts: int
    dog_km: int


class AttentionDogRead(BaseModel):
    id: UUID
    name: str
    dog_class: str
    availability: str | None
    dog_km: int
    dog_starts: int
    eligible_days: int
    worked_days: int
    recent_7d_km: int
    recent_14d_km: int
    longest_work_streak: int
    eligible_rest_streak: int
    workload_rate: float
    peer_median_rate: float
    reason: str


class AnalyticsOverviewRead(BaseModel):
    date_from: date
    date_to: date
    season_start: date
    season_end: date
    context_date: date
    summary: AnalyticsSummaryRead
    weekly: list[WeeklyAnalyticsRead]
    distance_breakdown: list[DistanceBreakdownRead]
    role_breakdown: list[RoleBreakdownRead]
    attention_population: int
    underused: list[AttentionDogRead]
    higher_workload: list[AttentionDogRead]


class AnalyticsDogRead(BaseModel):
    id: UUID
    name: str
    sex: str
    dog_class: str | None
    lifecycle: str | None
    availability: str | None
    housing_code: str | None
    housing_zone: str | None
    capabilities: list[str]
    dog_starts: int
    dog_km: int
    starts_5km: int
    starts_10km: int
    last_work_date: date | None
    worked_days: int
    eligible_days: int
    longest_work_streak: int
    eligible_rest_streak: int
    recent_7d_km: int
    recent_14d_km: int
    workload_status: str
    attention_reason: str | None


class AnalyticsDogsRead(BaseModel):
    date_from: date
    date_to: date
    context_date: date
    result_count: int
    items: list[AnalyticsDogRead]


class PopulationBucketRead(BaseModel):
    key: str
    label: str
    count: int


class PopulationCohortRead(BaseModel):
    birth_year: int
    total: int
    active: int
    archived: int
    litter_codes: list[str]


class PopulationHeadlineRead(BaseModel):
    total_represented: int
    active_dogs: int
    archived_dogs: int
    average_age_years: float
    median_age_years: float


class PopulationAnalyticsRead(BaseModel):
    snapshot_date: date
    season_start: date
    season_end: date
    distribution_basis: str
    headline: PopulationHeadlineRead
    sex: list[PopulationBucketRead]
    age_bands: list[PopulationBucketRead]
    birth_cohorts: list[PopulationCohortRead]
    classes: list[PopulationBucketRead]
    neuter_status: list[PopulationBucketRead]
    availability: list[PopulationBucketRead]
    capabilities: list[PopulationBucketRead]
    housing_areas: list[PopulationBucketRead]
