from collections.abc import Iterator
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.service import reset_demo_world
from app.main import app
from app.models import Dog, WorkParticipation, WorkSession
from app.services.analytics_service import AnalyticsService

FULL_RANGE = {"from": "2025-12-01", "to": "2026-03-31"}


@pytest.fixture(autouse=True)
def canonical_demo_world() -> Iterator[None]:
    with SessionLocal.begin() as session:
        reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def dog(name: str) -> tuple[int, str]:
    with SessionLocal() as session:
        row = session.execute(
            select(Dog.id, Dog.public_id).where(Dog.name == name)
        ).one()
    return row.id, str(row.public_id)


def add_actual(
    work_date: date,
    distance: int,
    *names: str,
    role: str | None = None,
    suffix: str = "one",
) -> None:
    with SessionLocal.begin() as session:
        work = WorkSession(
            source_reference=f"analytics-test-{work_date}-{distance}-{suffix}",
            work_date=work_date,
            start_time=time(9, 0),
            distance_km=distance,
            activity_type="sled_training",
            label="Analytics fixture",
            revision=1,
        )
        session.add(work)
        session.flush()
        for name in names:
            dog_id = session.scalar(select(Dog.id).where(Dog.name == name))
            assert dog_id is not None
            session.add(
                WorkParticipation(
                    session_id=work.id,
                    dog_id=dog_id,
                    assigned_role=role,
                )
            )


def test_full_season_metric_semantics_and_distance_breakdown(
    client: TestClient,
) -> None:
    body = client.get("/api/v1/analytics/overview", params=FULL_RANGE).json()
    assert body["summary"] == {
        "sessions": 140,
        "dogs_worked": 36,
        "dog_starts": 1120,
        "dog_km": 8400,
        "average_km_per_worked_dog": 233.3,
        "average_km_per_start": 7.5,
        "starts_5km": 560,
        "starts_10km": 560,
        "max_daily_dog_km": 10,
    }
    assert body["distance_breakdown"] == [
        {"distance_km": 5, "dog_starts": 560, "dog_km": 2800},
        {"distance_km": 10, "dog_starts": 560, "dog_km": 5600},
    ]
    assert sum(item["dog_starts"] for item in body["role_breakdown"]) == 1120


def test_reference_population_distributions_and_age_semantics(
    client: TestClient,
) -> None:
    body = client.get(
        "/api/v1/analytics/population", params={"date": "2026-03-31"}
    ).json()
    assert body["headline"] == {
        "total_represented": 60,
        "active_dogs": 50,
        "archived_dogs": 10,
        "average_age_years": 3.8,
        "median_age_years": 3.1,
    }
    for key in ("sex", "age_bands", "classes", "neuter_status", "availability"):
        assert sum(item["count"] for item in body[key]) == 50
    assert {item["key"]: item["count"] for item in body["classes"]} == {
        "puppy": 10,
        "junior": 6,
        "training": 8,
        "standard": 26,
    }
    assert {item["key"]: item["count"] for item in body["availability"]} == {
        "available": 46,
        "injured": 1,
        "rest": 1,
        "restricted": 1,
        "retired": 1,
    }
    assert {item["key"]: item["count"] for item in body["capabilities"]} == {
        "lead": 13,
        "team": 34,
        "wheel": 16,
    }
    assert sum(item["count"] for item in body["housing_areas"]) == 50


def test_population_excludes_unborn_and_resolves_class_and_lifecycle_boundaries(
    client: TestClient,
) -> None:
    before_birth = client.get(
        "/api/v1/analytics/population", params={"date": "2026-01-11"}
    ).json()
    on_birth = client.get(
        "/api/v1/analytics/population", params={"date": "2026-01-12"}
    ).json()
    assert before_birth["headline"]["total_represented"] == 50
    assert on_birth["headline"]["total_represented"] == 55

    jan31 = client.get(
        "/api/v1/analytics/population", params={"date": "2026-01-31"}
    ).json()
    feb1 = client.get(
        "/api/v1/analytics/population", params={"date": "2026-02-01"}
    ).json()
    jan_classes = {item["key"]: item["count"] for item in jan31["classes"]}
    feb_classes = {item["key"]: item["count"] for item in feb1["classes"]}
    assert jan_classes["training"] == feb_classes["training"] + 2
    assert jan_classes["standard"] + 2 == feb_classes["standard"]

    before_archive = client.get(
        "/api/v1/analytics/population", params={"date": "2025-12-14"}
    ).json()["headline"]
    on_archive = client.get(
        "/api/v1/analytics/population", params={"date": "2025-12-15"}
    ).json()["headline"]
    assert on_archive["active_dogs"] == before_archive["active_dogs"] - 1
    assert on_archive["archived_dogs"] == before_archive["archived_dogs"] + 1


def test_population_matches_reference_date_map_and_registry_projection(
    client: TestClient,
) -> None:
    population = client.get(
        "/api/v1/analytics/population", params={"date": "2026-03-31"}
    ).json()
    kennel_map = client.get("/api/v1/kennel-map", params={"date": "2026-03-31"}).json()
    registry = client.get("/api/v1/dogs").json()
    assert population["headline"]["active_dogs"] == registry["summary"]["total"]
    assert (
        population["headline"]["active_dogs"] == kennel_map["summary"]["resident_dogs"]
    )
    assert {item["key"]: item["count"] for item in population["classes"]} == kennel_map[
        "summary"
    ]["class_counts"]
    assert {
        item["key"]: item["count"] for item in population["availability"]
    } == kennel_map["summary"]["availability_counts"]


def test_analytics_queries_are_bounded() -> None:
    statements: list[str] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with SessionLocal() as session:
            service = AnalyticsService(session, DemoClock.from_settings(get_settings()))
            overview = service.overview(date(2025, 12, 1), date(2026, 3, 31))
            assert overview.summary.dog_starts == 1120
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    assert len(statements) <= 10


def test_one_session_multiple_dogs_and_multiple_starts_one_worked_day(
    client: TestClient,
) -> None:
    add_actual(date(2026, 3, 29), 10, "Atlas", "Aurora", suffix="first")
    body = client.get(
        "/api/v1/analytics/overview",
        params={"from": "2026-03-29", "to": "2026-03-29"},
    ).json()
    assert body["summary"]["sessions"] == 1
    assert body["summary"]["dogs_worked"] == 2
    assert body["summary"]["dog_starts"] == 2
    assert body["summary"]["dog_km"] == 20

    add_actual(date(2026, 3, 29), 5, "Atlas", suffix="second")
    dogs = client.get(
        "/api/v1/analytics/dogs",
        params={"from": "2026-03-29", "to": "2026-03-29", "search": "Atlas"},
    ).json()
    atlas = dogs["items"][0]
    assert (atlas["dog_starts"], atlas["dog_km"], atlas["worked_days"]) == (2, 15, 1)


def test_weekly_calendar_boundaries_zero_week_and_consistency(
    client: TestClient,
) -> None:
    body = client.get("/api/v1/analytics/overview", params=FULL_RANGE).json()
    assert body["weekly"][0]["week_start"] == "2025-12-01"
    assert body["weekly"][-1]["week_start"] == "2026-03-30"
    assert body["weekly"][-1]["period_end"] == "2026-03-31"
    assert sum(item["dog_starts"] for item in body["weekly"]) == 1120
    assert sum(item["dog_km"] for item in body["weekly"]) == 8400

    empty = client.get(
        "/api/v1/analytics/overview",
        params={"from": "2026-03-29", "to": "2026-03-29"},
    ).json()
    assert len(empty["weekly"]) == 1
    assert empty["weekly"][0]["week_start"] == "2026-03-23"
    assert empty["weekly"][0]["dog_starts"] == 0


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [
        ("2026-03-31", "2026-03-01"),
        ("2025-11-30", "2026-03-01"),
        ("2026-03-01", "2026-04-01"),
    ],
)
def test_analytics_range_validation(
    client: TestClient, date_from: str, date_to: str
) -> None:
    response = client.get(
        "/api/v1/analytics/overview",
        params={"from": date_from, "to": date_to},
    )
    assert response.status_code == 422


def test_relevant_zero_work_dogs_and_class_status_aware_attention(
    client: TestClient,
) -> None:
    dogs = client.get("/api/v1/analytics/dogs", params=FULL_RANGE).json()["items"]
    by_name = {item["name"]: item for item in dogs}
    assert by_name["Sanchez"]["dog_km"] == 0
    assert by_name["Sanchez"]["workload_status"] == "not_applicable"
    assert by_name["Taro"]["dog_km"] == 0
    assert by_name["Taro"]["workload_status"] == "not_applicable"
    assert by_name["Orion"]["workload_status"] == "balanced"
    assert by_name["Maple"]["eligible_days"] < by_name["Atlas"]["eligible_days"]
    assert by_name["Fjord"]["workload_status"] == "not_applicable"
    assert by_name["Django"]["dog_km"] == 35
    assert by_name["Django"]["lifecycle"] == "archived"

    overview = client.get("/api/v1/analytics/overview", params=FULL_RANGE).json()
    attention_names = {
        item["name"] for item in overview["underused"] + overview["higher_workload"]
    }
    assert not {"Sanchez", "Taro", "Fjord", "Django"} & attention_names
    assert {"Aurora", "Maple"} <= {item["name"] for item in overview["higher_workload"]}
    assert {"Cedar", "Delta", "Harbor"} == {
        item["name"] for item in overview["underused"]
    }


def test_effective_unavailability_changes_eligible_opportunity(
    client: TestClient,
) -> None:
    december = client.get(
        "/api/v1/analytics/dogs",
        params={"from": "2025-12-01", "to": "2025-12-31"},
    ).json()["items"]
    by_name = {item["name"]: item for item in december}
    assert by_name["Maple"]["eligible_days"] == 19
    assert by_name["Atlas"]["eligible_days"] == 31

    march = client.get(
        "/api/v1/analytics/dogs",
        params={"from": "2026-03-01", "to": "2026-03-31"},
    ).json()["items"]
    march_by_name = {item["name"]: item for item in march}
    assert march_by_name["Fjord"]["eligible_days"] == 0
    assert march_by_name["Aurora"]["eligible_days"] == 26

    before_rest = client.get(
        "/api/v1/analytics/dogs",
        params={"from": "2026-03-01", "to": "2026-03-04", "search": "Aurora"},
    ).json()["items"][0]
    during_rest = client.get(
        "/api/v1/analytics/dogs",
        params={"from": "2026-03-05", "to": "2026-03-08", "search": "Aurora"},
    ).json()["items"][0]
    assert before_rest["eligible_rest_streak"] == 1
    assert during_rest["eligible_days"] == 0
    assert during_rest["eligible_rest_streak"] == 0
    assert by_name["Atlas"]["longest_work_streak"] == 2


def test_dog_profile_and_analytics_share_participation_totals(
    client: TestClient,
) -> None:
    _, aurora_id = dog("Aurora")
    profile = client.get(f"/api/v1/dogs/{aurora_id}/work").json()["summary"]
    analytics = client.get(
        "/api/v1/analytics/dogs", params={**FULL_RANGE, "search": "Aurora"}
    ).json()["items"][0]
    assert analytics["dog_km"] == profile["total_km"]
    assert analytics["dog_starts"] == profile["starts"]
    assert analytics["starts_5km"] == profile["starts_5km"]
    assert analytics["starts_10km"] == profile["starts_10km"]


def test_role_breakdown_uses_recorded_role_and_keeps_unpositioned(
    client: TestClient,
) -> None:
    add_actual(date(2026, 3, 29), 5, "Atlas", role=None)
    body = client.get(
        "/api/v1/analytics/overview",
        params={"from": "2026-03-29", "to": "2026-03-29"},
    ).json()
    roles = {item["role"]: item for item in body["role_breakdown"]}
    assert roles["unpositioned"] == {
        "role": "unpositioned",
        "dog_starts": 1,
        "dog_km": 5,
    }


def test_planned_and_not_run_training_contribute_no_actual_work(
    client: TestClient,
) -> None:
    _, atlas_id = dog("Atlas")
    plan = client.post(
        "/api/v1/daily-plans/2026-03-29/activities",
        json={
            "activity_type": "training",
            "start_time": "08:30:00",
            "title": "Planned only",
            "distance_km": 10,
            "notes": None,
            "participant_ids": [atlas_id],
            "expected_revision": None,
        },
    )
    assert plan.status_code == 200, plan.text
    activity_id = plan.json()["activities"][0]["id"]
    params = {"from": "2026-03-29", "to": "2026-03-29"}
    assert (
        client.get("/api/v1/analytics/overview", params=params).json()["summary"][
            "dog_starts"
        ]
        == 0
    )

    not_run = client.post(
        f"/api/v1/daily-entry/2026-03-29/planned-activities/{activity_id}/not-run"
    )
    assert not_run.status_code == 200, not_run.text
    assert (
        client.get("/api/v1/analytics/overview", params=params).json()["summary"][
            "dog_starts"
        ]
        == 0
    )


def test_future_actual_work_does_not_change_historical_analytics(
    client: TestClient,
) -> None:
    params = {"from": "2026-03-01", "to": "2026-03-20"}
    before = client.get("/api/v1/analytics/overview", params=params).json()
    add_actual(date(2026, 3, 29), 10, "Atlas", suffix="future")
    after = client.get("/api/v1/analytics/overview", params=params).json()
    assert after == before


def test_dog_search_class_filter_and_sorting(client: TestClient) -> None:
    training = client.get(
        "/api/v1/analytics/dogs",
        params={**FULL_RANGE, "dog_class": "training", "sort": "lowest_km"},
    ).json()
    assert training["result_count"] >= 8
    assert {item["dog_class"] for item in training["items"]} == {"training"}
    assert [item["dog_km"] for item in training["items"]] == sorted(
        item["dog_km"] for item in training["items"]
    )
    search = client.get(
        "/api/v1/analytics/dogs", params={**FULL_RANGE, "search": "aUrOrA"}
    ).json()
    assert [item["name"] for item in search["items"]] == ["Aurora"]


def test_actual_edit_and_delete_immediately_change_analytics(
    client: TestClient,
) -> None:
    _, atlas_id = dog("Atlas")
    created = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json={
            "distance_km": 10,
            "start_time": "09:00:00",
            "label": "Analytics round trip",
            "note": None,
            "participants": [{"dog_id": atlas_id}],
        },
    )
    assert created.status_code == 200, created.text
    actual = created.json()["sessions"][0]
    params = {"from": "2026-03-29", "to": "2026-03-29"}
    assert (
        client.get("/api/v1/analytics/overview", params=params).json()["summary"][
            "dog_km"
        ]
        == 10
    )

    changed = client.patch(
        f"/api/v1/daily-entry/2026-03-29/sessions/{actual['id']}",
        json={
            "expected_revision": actual["revision"],
            "distance_km": 5,
            "start_time": "09:00:00",
            "label": "Edited",
            "note": None,
            "participants": [{"dog_id": atlas_id}],
        },
    )
    assert changed.status_code == 200
    revised = changed.json()["sessions"][0]
    assert (
        client.get("/api/v1/analytics/overview", params=params).json()["summary"][
            "dog_km"
        ]
        == 5
    )

    deleted = client.delete(
        f"/api/v1/daily-entry/2026-03-29/sessions/{actual['id']}",
        params={"expected_revision": revised["revision"]},
    )
    assert deleted.status_code == 200
    assert (
        client.get("/api/v1/analytics/overview", params=params).json()["summary"][
            "dog_km"
        ]
        == 0
    )
