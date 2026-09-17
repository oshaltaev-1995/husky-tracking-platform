from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.schemas.analytics import AttentionDogRead, WeeklyAnalyticsRead


class DashboardContextRead(BaseModel):
    selected_date: date
    season_start: date
    season_end: date
    reference_date: date
    season_label: str


class DashboardPopulationRead(BaseModel):
    active_dogs: int
    class_counts: dict[str, int]
    available_dogs: int
    unavailable_dogs: int
    availability_counts: dict[str, int]
    resident_dogs: int
    occupied_locations: int
    housing_areas: dict[str, int]


class DashboardUnavailableDogRead(BaseModel):
    id: UUID
    name: str
    availability: str
    housing_code: str


class DashboardTrainingRead(BaseModel):
    id: UUID
    title: str
    distance_km: int
    participant_count: int
    team_count: int
    arranged_dog_count: int
    actual_status: str


class DashboardPlanRead(BaseModel):
    exists: bool
    activities_count: int
    activity_counts: dict[str, int]
    planned_dogs: int
    planned_dog_km: int
    training_with_saved_teams: int
    training_without_saved_teams: int
    notes_preview: str | None
    status_counts: dict[str, int]
    training: list[DashboardTrainingRead]


class DashboardActualRead(BaseModel):
    sessions: int
    dogs_worked: int
    dog_starts: int
    dog_km: int


class DashboardAttentionRead(BaseModel):
    date_from: date
    date_to: date
    label: str
    underused_count: int
    higher_workload_count: int
    underused: list[AttentionDogRead]
    higher_workload: list[AttentionDogRead]


class DashboardRead(BaseModel):
    context: DashboardContextRead
    population: DashboardPopulationRead
    unavailable_dogs: list[DashboardUnavailableDogRead]
    plan: DashboardPlanRead
    actual: DashboardActualRead
    attention: DashboardAttentionRead
    recent_weekly: list[WeeklyAnalyticsRead]
