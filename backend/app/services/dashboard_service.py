from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.demo_clock import DemoClock
from app.models.enums import PlannedActivityType
from app.schemas.dashboard import (
    DashboardActualRead,
    DashboardAttentionRead,
    DashboardContextRead,
    DashboardPlanRead,
    DashboardPopulationRead,
    DashboardRead,
    DashboardTrainingRead,
    DashboardUnavailableDogRead,
)
from app.services.analytics_service import AnalyticsService
from app.services.daily_entry_service import DailyEntryService
from app.services.daily_plan_service import DailyPlanService
from app.services.kennel_map_read_service import KennelMapReadService


class DashboardService:
    """Compose existing domain projections into one operational home payload."""

    def __init__(
        self, session: Session, clock: DemoClock, workspace_id: int | None = None
    ) -> None:
        self.clock = clock
        self.analytics = AnalyticsService(session, clock, workspace_id)
        self.plans = DailyPlanService(session, clock, workspace_id)
        self.entries = DailyEntryService(session, clock, workspace_id)
        self.kennel = KennelMapReadService(session, clock)

    def read(self, selected_date: date) -> DashboardRead:
        self.analytics.validate_range(selected_date, selected_date)
        population = self.analytics.population(selected_date)
        kennel = self.kennel.snapshot(selected_date)
        plan = self.plans.read(selected_date)
        entry = self.entries.read(selected_date)

        attention_start = max(
            self.clock.season_start, selected_date - timedelta(days=13)
        )
        attention = self.analytics.overview(attention_start, selected_date)

        current_week_start = selected_date - timedelta(days=selected_date.weekday())
        trend_start = max(
            self.clock.season_start, current_week_start - timedelta(weeks=5)
        )
        recent_weekly = self.analytics.weekly(trend_start, selected_date)

        class_counts = {item.key: item.count for item in population.classes}
        availability_counts = {item.key: item.count for item in population.availability}
        housing_areas = {item.label: item.count for item in population.housing_areas}
        unavailable_dogs = sorted(
            (
                DashboardUnavailableDogRead(
                    id=resident.id,
                    name=resident.name,
                    availability=resident.availability or "unknown",
                    housing_code=resident.housing_code,
                )
                for location in kennel.locations
                for resident in location.residents
                if resident.availability != "available"
            ),
            key=lambda item: (item.availability, item.name),
        )

        activity_counts = Counter(
            activity.activity_type.value for activity in plan.activities
        )
        participant_ids = {
            participant.id
            for activity in plan.activities
            for participant in activity.participants
        }
        planned_dog_km = sum(
            (activity.distance_km or 0) * len(activity.participants)
            for activity in plan.activities
            if activity.activity_type is PlannedActivityType.TRAINING
        )
        status_counts = Counter(
            activity.actual_status for activity in entry.planned_activities
        )
        actual_by_id = {activity.id: activity for activity in entry.planned_activities}
        training = [
            DashboardTrainingRead(
                id=activity.id,
                title=activity.title,
                distance_km=activity.distance_km or 0,
                participant_count=len(activity.participants),
                team_count=activity.team_count,
                arranged_dog_count=activity.arranged_dog_count,
                actual_status=actual_by_id[activity.id].actual_status,
            )
            for activity in plan.activities
            if activity.activity_type is PlannedActivityType.TRAINING
        ]
        training_with_teams = sum(item.team_count > 0 for item in training)

        return DashboardRead(
            context=DashboardContextRead(
                selected_date=selected_date,
                season_start=self.clock.season_start,
                season_end=self.clock.season_end,
                reference_date=self.clock.reference_date,
                season_label="Winter 2025–2026",
            ),
            population=DashboardPopulationRead(
                active_dogs=population.headline.active_dogs,
                class_counts=class_counts,
                available_dogs=availability_counts.get("available", 0),
                unavailable_dogs=sum(
                    count
                    for status, count in availability_counts.items()
                    if status != "available"
                ),
                availability_counts=availability_counts,
                resident_dogs=kennel.summary.resident_dogs,
                occupied_locations=kennel.summary.occupied_locations,
                housing_areas=housing_areas,
            ),
            unavailable_dogs=unavailable_dogs,
            plan=DashboardPlanRead(
                exists=plan.exists,
                activities_count=len(plan.activities),
                activity_counts=dict(activity_counts),
                planned_dogs=len(participant_ids),
                planned_dog_km=planned_dog_km,
                training_with_saved_teams=training_with_teams,
                training_without_saved_teams=len(training) - training_with_teams,
                notes_preview=self._preview(plan.notes),
                status_counts=dict(status_counts),
                training=training,
            ),
            actual=DashboardActualRead(
                sessions=entry.summary.actual_sessions,
                dogs_worked=entry.summary.dogs_worked,
                dog_starts=entry.summary.dog_starts,
                dog_km=entry.summary.total_dog_km,
            ),
            attention=DashboardAttentionRead(
                date_from=attention_start,
                date_to=selected_date,
                label="Previous 14 days",
                underused_count=len(attention.underused),
                higher_workload_count=len(attention.higher_workload),
                underused=attention.underused[:3],
                higher_workload=attention.higher_workload[:3],
            ),
            recent_weekly=recent_weekly,
        )

    @staticmethod
    def _preview(notes: str | None) -> str | None:
        if notes is None:
            return None
        return notes if len(notes) <= 160 else f"{notes[:157].rstrip()}…"
