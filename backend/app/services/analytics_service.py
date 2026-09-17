from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.demo_clock import DemoClock
from app.domain.analytics import summarize_work_distances
from app.models import Dog, HousingAssignment, WorkParticipation, WorkSession
from app.schemas.analytics import (
    AnalyticsDogRead,
    AnalyticsDogSort,
    AnalyticsDogsRead,
    AnalyticsOverviewRead,
    AnalyticsSummaryRead,
    AttentionDogRead,
    DistanceBreakdownRead,
    PopulationAnalyticsRead,
    PopulationBucketRead,
    PopulationCohortRead,
    PopulationHeadlineRead,
    RoleBreakdownRead,
    WeeklyAnalyticsRead,
)
from app.services.effective_state import EffectiveDogState

UNDERUSED_RATE_RATIO = 0.95
HIGHER_WORKLOAD_RATE_RATIO = 1.15
WORKLOAD_CLASSES = {"training", "standard"}


class AnalyticsRangeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkRow:
    session_id: int
    work_date: date
    distance_km: int
    dog_id: int
    role: str | None


@dataclass(slots=True)
class DogMetrics:
    starts: int = 0
    dog_km: int = 0
    starts_5km: int = 0
    starts_10km: int = 0
    last_work_date: date | None = None
    worked_dates: set[date] | None = None
    recent_7d_km: int = 0
    recent_14d_km: int = 0

    def __post_init__(self) -> None:
        if self.worked_dates is None:
            self.worked_dates = set()


@dataclass(frozen=True, slots=True)
class DogAnalysis:
    dog: Dog
    dog_class: str | None
    lifecycle: str | None
    availability: str | None
    housing_code: str | None
    housing_zone: str | None
    metrics: DogMetrics
    presence_days: int
    eligible_days: int
    worked_days: int
    longest_work_streak: int
    eligible_rest_streak: int
    workload_rate: float
    attention_eligible: bool


def _dates(date_from: date, date_to: date) -> list[date]:
    return [
        date_from + timedelta(days=offset)
        for offset in range((date_to - date_from).days + 1)
    ]


def _summary(session_ids: set[int], rows: list[WorkRow]) -> AnalyticsSummaryRead:
    dogs = {row.dog_id for row in rows}
    totals = summarize_work_distances(row.distance_km for row in rows)
    daily: dict[tuple[int, date], int] = defaultdict(int)
    for row in rows:
        daily[(row.dog_id, row.work_date)] += row.distance_km
    return AnalyticsSummaryRead(
        sessions=len(session_ids),
        dogs_worked=len(dogs),
        dog_starts=totals.dog_starts,
        dog_km=totals.dog_km,
        average_km_per_worked_dog=(
            round(totals.dog_km / len(dogs), 1) if dogs else 0.0
        ),
        average_km_per_start=totals.average_km_per_start,
        starts_5km=totals.starts_5km,
        starts_10km=totals.starts_10km,
        max_daily_dog_km=max(daily.values(), default=0),
    )


def _longest_work_streak(worked_dates: set[date], period: list[date]) -> int:
    longest = current = 0
    for day in period:
        if day in worked_dates:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


class AnalyticsService:
    """Actual-ledger analytics with bounded work and dog-state projections."""

    def __init__(self, session: Session, clock: DemoClock) -> None:
        self.session = session
        self.clock = clock

    def validate_range(self, date_from: date, date_to: date) -> None:
        if date_from > date_to:
            raise AnalyticsRangeError("From date must be on or before To date.")
        if date_from < self.clock.season_start or date_to > self.clock.season_end:
            raise AnalyticsRangeError(
                "Analytics dates must stay inside the Winter 2025–2026 demo season."
            )

    def _work(
        self, date_from: date, date_to: date
    ) -> tuple[dict[int, date], list[WorkRow]]:
        session_rows = self.session.execute(
            select(WorkSession.id, WorkSession.work_date).where(
                WorkSession.work_date >= date_from,
                WorkSession.work_date <= date_to,
            )
        ).all()
        rows = self.session.execute(
            select(
                WorkSession.id,
                WorkSession.work_date,
                WorkSession.distance_km,
                WorkParticipation.dog_id,
                WorkParticipation.assigned_role,
            )
            .join(WorkParticipation, WorkParticipation.session_id == WorkSession.id)
            .where(
                WorkSession.work_date >= date_from,
                WorkSession.work_date <= date_to,
            )
            .order_by(WorkSession.work_date, WorkSession.id, WorkParticipation.dog_id)
        ).all()
        return (
            {row.id: row.work_date for row in session_rows},
            [
                WorkRow(
                    session_id=row.id,
                    work_date=row.work_date,
                    distance_km=row.distance_km,
                    dog_id=row.dog_id,
                    role=row.assigned_role,
                )
                for row in rows
            ],
        )

    def _dogs(self) -> list[Dog]:
        return list(
            self.session.scalars(
                select(Dog).options(
                    selectinload(Dog.litter),
                    selectinload(Dog.class_periods),
                    selectinload(Dog.lifecycle_periods),
                    selectinload(Dog.availability_periods),
                    selectinload(Dog.housing_assignments).selectinload(
                        HousingAssignment.location
                    ),
                    selectinload(Dog.role_capabilities),
                )
            ).unique()
        )

    def population(self, snapshot_date: date) -> PopulationAnalyticsRead:
        self.validate_range(snapshot_date, snapshot_date)
        dogs = [dog for dog in self._dogs() if dog.birth_date <= snapshot_date]
        state = EffectiveDogState(snapshot_date)
        lifecycle_by_id = {dog.id: state.lifecycle(dog) for dog in dogs}
        active = [dog for dog in dogs if lifecycle_by_id[dog.id] == "active"]
        archived = [dog for dog in dogs if lifecycle_by_id[dog.id] == "archived"]

        def full_age(dog: Dog) -> int:
            return (
                snapshot_date.year
                - dog.birth_date.year
                - (
                    (snapshot_date.month, snapshot_date.day)
                    < (dog.birth_date.month, dog.birth_date.day)
                )
            )

        ages = [(snapshot_date - dog.birth_date).days / 365.2425 for dog in active]

        def buckets(
            values: dict[str, int], labels: dict[str, str], order: list[str]
        ) -> list[PopulationBucketRead]:
            return [
                PopulationBucketRead(
                    key=key,
                    label=labels.get(key, key.replace("_", " ").title()),
                    count=values.get(key, 0),
                )
                for key in order
            ]

        sex_counts: dict[str, int] = defaultdict(int)
        class_counts: dict[str, int] = defaultdict(int)
        availability_counts: dict[str, int] = defaultdict(int)
        neuter_counts: dict[str, int] = defaultdict(int)
        age_counts: dict[str, int] = defaultdict(int)
        capability_counts: dict[str, int] = defaultdict(int)
        housing_counts: dict[str, int] = defaultdict(int)
        for dog in active:
            sex_counts[dog.sex] += 1
            dog_class, _ = state.dog_class(dog)
            class_counts[dog_class or "unknown"] += 1
            availability_counts[state.availability(dog) or "unknown"] += 1
            neutered = dog.is_neutered and (
                dog.neutered_on is None or dog.neutered_on <= snapshot_date
            )
            neuter_counts["neutered"] += int(neutered)
            neuter_counts["intact"] += int(not neutered)
            age = full_age(dog)
            if age < 1:
                age_counts["under_1"] += 1
            elif age <= 2:
                age_counts["1_2"] += 1
            elif age <= 5:
                age_counts["3_5"] += 1
            elif age <= 8:
                age_counts["6_8"] += 1
            else:
                age_counts["9_plus"] += 1
            for capability in dog.role_capabilities:
                capability_counts[capability.role] += 1
            housing = state.housing(dog)
            if not housing:
                housing_counts["unassigned"] += 1
            elif housing.location.location_type == "puppy_area":
                housing_counts[housing.location.code] += 1
            else:
                housing_counts[f"zone_{housing.location.zone.lower()}"] += 1

        cohorts: list[PopulationCohortRead] = []
        for year in sorted({dog.birth_date.year for dog in dogs}):
            members = [dog for dog in dogs if dog.birth_date.year == year]
            cohorts.append(
                PopulationCohortRead(
                    birth_year=year,
                    total=len(members),
                    active=sum(lifecycle_by_id[dog.id] == "active" for dog in members),
                    archived=sum(
                        lifecycle_by_id[dog.id] == "archived" for dog in members
                    ),
                    litter_codes=sorted(
                        {dog.litter.code for dog in members if dog.litter is not None}
                    ),
                )
            )

        housing_order = ["zone_a", "zone_b", "PUPPY-A", "PUPPY-B"]
        if housing_counts.get("unassigned"):
            housing_order.append("unassigned")
        return PopulationAnalyticsRead(
            snapshot_date=snapshot_date,
            season_start=self.clock.season_start,
            season_end=self.clock.season_end,
            distribution_basis="active dogs on snapshot date",
            headline=PopulationHeadlineRead(
                total_represented=len(dogs),
                active_dogs=len(active),
                archived_dogs=len(archived),
                average_age_years=(round(sum(ages) / len(ages), 1) if ages else 0.0),
                median_age_years=(round(float(median(ages)), 1) if ages else 0.0),
            ),
            sex=buckets(
                sex_counts,
                {"female": "Female", "male": "Male"},
                ["female", "male"],
            ),
            age_bands=buckets(
                age_counts,
                {
                    "under_1": "Under 1 year",
                    "1_2": "1–2 years",
                    "3_5": "3–5 years",
                    "6_8": "6–8 years",
                    "9_plus": "9+ years",
                },
                ["under_1", "1_2", "3_5", "6_8", "9_plus"],
            ),
            birth_cohorts=cohorts,
            classes=buckets(
                class_counts,
                {},
                ["puppy", "junior", "training", "standard"],
            ),
            neuter_status=buckets(
                neuter_counts,
                {"neutered": "Neutered / spayed", "intact": "Intact"},
                ["neutered", "intact"],
            ),
            availability=buckets(
                availability_counts,
                {},
                ["available", "injured", "rest", "restricted", "retired"],
            ),
            capabilities=buckets(
                capability_counts,
                {
                    "lead": "Lead capable",
                    "team": "Team capable",
                    "wheel": "Wheel capable",
                },
                ["lead", "team", "wheel"],
            ),
            housing_areas=buckets(
                housing_counts,
                {
                    "zone_a": "Zone A",
                    "zone_b": "Zone B",
                    "PUPPY-A": "Puppy A",
                    "PUPPY-B": "Puppy B",
                    "unassigned": "Unassigned",
                },
                housing_order,
            ),
        )

    def _dog_analyses(
        self, dogs: list[Dog], rows: list[WorkRow], date_from: date, date_to: date
    ) -> list[DogAnalysis]:
        period = _dates(date_from, date_to)
        recent_7d_start = max(date_from, date_to - timedelta(days=6))
        recent_14d_start = max(date_from, date_to - timedelta(days=13))
        metrics_by_dog: dict[int, DogMetrics] = defaultdict(DogMetrics)
        for row in rows:
            item = metrics_by_dog[row.dog_id]
            item.starts += 1
            item.dog_km += row.distance_km
            item.starts_5km += int(row.distance_km == 5)
            item.starts_10km += int(row.distance_km == 10)
            item.last_work_date = max(
                item.last_work_date or row.work_date, row.work_date
            )
            assert item.worked_dates is not None
            item.worked_dates.add(row.work_date)
            if row.work_date >= recent_7d_start:
                item.recent_7d_km += row.distance_km
            if row.work_date >= recent_14d_start:
                item.recent_14d_km += row.distance_km

        result: list[DogAnalysis] = []
        end_state = EffectiveDogState(date_to)
        for dog in dogs:
            metrics = metrics_by_dog[dog.id]
            worked_dates = metrics.worked_dates or set()
            presence_days = 0
            eligible_days = 0
            eligible_by_day: dict[date, bool] = {}
            for day in period:
                state = EffectiveDogState(day)
                lifecycle = state.lifecycle(dog)
                dog_class, _ = state.dog_class(dog)
                availability = state.availability(dog)
                present = dog.birth_date <= day and lifecycle == "active"
                eligible = (
                    present
                    and dog_class in WORKLOAD_CLASSES
                    and availability == "available"
                )
                presence_days += int(present)
                eligible_days += int(eligible)
                eligible_by_day[day] = eligible

            rest_streak = 0
            for day in reversed(period):
                if not eligible_by_day[day] or day in worked_dates:
                    break
                rest_streak += 1

            dog_class, _ = end_state.dog_class(dog, historical_fallback=True)
            lifecycle = end_state.lifecycle(dog)
            availability = end_state.availability(dog)
            housing = end_state.housing(dog)
            attention_eligible = (
                lifecycle == "active"
                and dog_class in WORKLOAD_CLASSES
                and availability != "retired"
                and eligible_days > 0
            )
            result.append(
                DogAnalysis(
                    dog=dog,
                    dog_class=dog_class,
                    lifecycle=lifecycle,
                    availability=availability,
                    housing_code=housing.location.code if housing else None,
                    housing_zone=housing.location.zone if housing else None,
                    metrics=metrics,
                    presence_days=presence_days,
                    eligible_days=eligible_days,
                    worked_days=len(worked_dates),
                    longest_work_streak=_longest_work_streak(worked_dates, period),
                    eligible_rest_streak=rest_streak,
                    workload_rate=(
                        round(metrics.dog_km / eligible_days * 7, 2)
                        if eligible_days
                        else 0.0
                    ),
                    attention_eligible=attention_eligible,
                )
            )
        return result

    @staticmethod
    def _peer_medians(analyses: list[DogAnalysis]) -> dict[str, float]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for item in analyses:
            if item.attention_eligible and item.dog_class:
                grouped[item.dog_class].append(item.workload_rate)
        return {
            dog_class: round(float(median(values)), 2)
            for dog_class, values in grouped.items()
            if values
        }

    @staticmethod
    def _status(item: DogAnalysis, peer_medians: dict[str, float]) -> str:
        if not item.attention_eligible or not item.dog_class:
            return "not_applicable"
        peer = peer_medians.get(item.dog_class, 0.0)
        if peer <= 0:
            return "balanced"
        if item.workload_rate < peer * UNDERUSED_RATE_RATIO:
            return "underused"
        if item.workload_rate > peer * HIGHER_WORKLOAD_RATE_RATIO:
            return "higher"
        return "balanced"

    @staticmethod
    def _reason(item: DogAnalysis, status: str, peer: float) -> str | None:
        if status == "underused":
            rest = (
                f" · {item.eligible_rest_streak} eligible days since work"
                if item.eligible_rest_streak
                else ""
            )
            return (
                f"{item.metrics.dog_km} km across {item.eligible_days} eligible days"
                f"{rest} · below {item.dog_class} peer pace"
            )
        if status == "higher":
            return (
                f"{item.metrics.dog_km} km · {item.metrics.recent_14d_km} km in the "
                f"final 14 days · above {item.dog_class} peer pace"
            )
        if status == "not_applicable" and item.dog_class in {"puppy", "junior"}:
            return f"{item.dog_class.title()} · not in regular sled-work comparison"
        if status == "not_applicable" and item.availability == "retired":
            return "Retired · historical workload retained outside current attention"
        if status == "not_applicable" and item.lifecycle == "archived":
            return "Archived · historical workload retained outside current attention"
        if peer == 0:
            return "No peer workload in this range"
        return None

    def _analysis(
        self, date_from: date, date_to: date
    ) -> tuple[dict[int, date], list[WorkRow], list[DogAnalysis], dict[str, float]]:
        self.validate_range(date_from, date_to)
        session_ids, rows = self._work(date_from, date_to)
        analyses = self._dog_analyses(self._dogs(), rows, date_from, date_to)
        return session_ids, rows, analyses, self._peer_medians(analyses)

    def overview(self, date_from: date, date_to: date) -> AnalyticsOverviewRead:
        session_ids, rows, analyses, peer_medians = self._analysis(date_from, date_to)
        weekly: list[WeeklyAnalyticsRead] = []
        week_start = date_from - timedelta(days=date_from.weekday())
        while week_start <= date_to:
            week_end = week_start + timedelta(days=6)
            week_rows = [row for row in rows if week_start <= row.work_date <= week_end]
            week_session_ids = {
                session_id
                for session_id, work_date in session_ids.items()
                if week_start <= work_date <= week_end
            }
            summary = _summary(week_session_ids, week_rows)
            weekly.append(
                WeeklyAnalyticsRead(
                    week_start=week_start,
                    week_end=week_end,
                    period_start=max(week_start, date_from),
                    period_end=min(week_end, date_to),
                    iso_week=week_start.isocalendar().week,
                    **summary.model_dump(),
                )
            )
            week_start += timedelta(days=7)

        attention: list[tuple[DogAnalysis, str, float]] = []
        for item in analyses:
            peer = peer_medians.get(item.dog_class or "", 0.0)
            attention.append((item, self._status(item, peer_medians), peer))

        def attention_read(item: DogAnalysis, peer: float) -> AttentionDogRead:
            reason = self._reason(item, self._status(item, peer_medians), peer)
            assert item.dog_class is not None and reason is not None
            return AttentionDogRead(
                id=item.dog.public_id,
                name=item.dog.name,
                dog_class=item.dog_class,
                availability=item.availability,
                dog_km=item.metrics.dog_km,
                dog_starts=item.metrics.starts,
                eligible_days=item.eligible_days,
                worked_days=item.worked_days,
                recent_7d_km=item.metrics.recent_7d_km,
                recent_14d_km=item.metrics.recent_14d_km,
                longest_work_streak=item.longest_work_streak,
                eligible_rest_streak=item.eligible_rest_streak,
                workload_rate=item.workload_rate,
                peer_median_rate=peer,
                reason=reason,
            )

        underused = [
            attention_read(item, peer)
            for item, status, peer in attention
            if status == "underused"
        ]
        higher = [
            attention_read(item, peer)
            for item, status, peer in attention
            if status == "higher"
        ]
        underused.sort(key=lambda item: (item.workload_rate, item.name))
        higher.sort(key=lambda item: (-item.workload_rate, item.name))

        role_counts: dict[str, list[int]] = {
            role: [0, 0] for role in ("lead", "team", "wheel", "unpositioned")
        }
        for row in rows:
            role = row.role or "unpositioned"
            role_counts[role][0] += 1
            role_counts[role][1] += row.distance_km

        return AnalyticsOverviewRead(
            date_from=date_from,
            date_to=date_to,
            season_start=self.clock.season_start,
            season_end=self.clock.season_end,
            context_date=date_to,
            summary=_summary(set(session_ids), rows),
            weekly=weekly,
            distance_breakdown=[
                DistanceBreakdownRead(
                    distance_km=distance,
                    dog_starts=sum(row.distance_km == distance for row in rows),
                    dog_km=sum(
                        row.distance_km for row in rows if row.distance_km == distance
                    ),
                )
                for distance in (5, 10)
            ],
            role_breakdown=[
                RoleBreakdownRead(
                    role=role,
                    dog_starts=values[0],
                    dog_km=values[1],
                )
                for role, values in role_counts.items()
            ],
            attention_population=sum(item.attention_eligible for item in analyses),
            underused=underused,
            higher_workload=higher,
        )

    def dogs(
        self,
        date_from: date,
        date_to: date,
        *,
        search: str | None,
        dog_class: str | None,
        sort: AnalyticsDogSort,
    ) -> AnalyticsDogsRead:
        _, _, analyses, peer_medians = self._analysis(date_from, date_to)
        items: list[AnalyticsDogRead] = []
        for item in analyses:
            if item.presence_days == 0 and item.metrics.starts == 0:
                continue
            status = self._status(item, peer_medians)
            peer = peer_medians.get(item.dog_class or "", 0.0)
            items.append(
                AnalyticsDogRead(
                    id=item.dog.public_id,
                    name=item.dog.name,
                    sex=item.dog.sex,
                    dog_class=item.dog_class,
                    lifecycle=item.lifecycle,
                    availability=item.availability,
                    housing_code=item.housing_code,
                    housing_zone=item.housing_zone,
                    capabilities=sorted(
                        role.role for role in item.dog.role_capabilities
                    ),
                    dog_starts=item.metrics.starts,
                    dog_km=item.metrics.dog_km,
                    starts_5km=item.metrics.starts_5km,
                    starts_10km=item.metrics.starts_10km,
                    last_work_date=item.metrics.last_work_date,
                    worked_days=item.worked_days,
                    eligible_days=item.eligible_days,
                    longest_work_streak=item.longest_work_streak,
                    eligible_rest_streak=item.eligible_rest_streak,
                    recent_7d_km=item.metrics.recent_7d_km,
                    recent_14d_km=item.metrics.recent_14d_km,
                    workload_status=status,
                    attention_reason=self._reason(item, status, peer),
                )
            )

        if search:
            needle = search.strip().casefold()
            items = [item for item in items if needle in item.name.casefold()]
        if dog_class:
            items = [item for item in items if item.dog_class == dog_class]

        if sort == AnalyticsDogSort.LOWEST_KM:
            items.sort(key=lambda item: (item.dog_km, item.name))
        elif sort == AnalyticsDogSort.MOST_STARTS:
            items.sort(key=lambda item: (-item.dog_starts, item.name))
        elif sort == AnalyticsDogSort.FEWEST_STARTS:
            items.sort(key=lambda item: (item.dog_starts, item.name))
        elif sort == AnalyticsDogSort.NAME:
            items.sort(key=lambda item: item.name)
        else:
            items.sort(key=lambda item: (-item.dog_km, item.name))
        return AnalyticsDogsRead(
            date_from=date_from,
            date_to=date_to,
            context_date=date_to,
            result_count=len(items),
            items=items,
        )
