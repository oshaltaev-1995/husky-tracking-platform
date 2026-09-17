from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.service import reset_demo_world
from app.main import app
from app.models import Dog
from app.services.dashboard_service import DashboardService


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


def dog_ids(*names: str) -> list[str]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Dog.name, Dog.public_id).where(Dog.name.in_(names))
        )
        by_name = {name: str(public_id) for name, public_id in rows}
    return [by_name[name] for name in names]


def test_reference_dashboard_reuses_canonical_projections(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard", params={"date": "2026-03-31"})
    assert response.status_code == 200
    body = response.json()
    assert body["context"]["selected_date"] == "2026-03-31"
    assert body["population"] == {
        "active_dogs": 50,
        "class_counts": {
            "puppy": 10,
            "junior": 6,
            "training": 8,
            "standard": 26,
        },
        "available_dogs": 46,
        "unavailable_dogs": 4,
        "availability_counts": {
            "available": 46,
            "injured": 1,
            "rest": 1,
            "restricted": 1,
            "retired": 1,
        },
        "resident_dogs": 50,
        "occupied_locations": 22,
        "housing_areas": {
            "Zone A": 20,
            "Zone B": 20,
            "Puppy A": 5,
            "Puppy B": 5,
        },
    }
    assert body["plan"]["exists"] is False
    assert body["actual"] == {
        "sessions": 2,
        "dogs_worked": 16,
        "dog_starts": 16,
        "dog_km": 120,
    }
    assert body["attention"]["date_from"] == "2026-03-18"
    assert body["attention"]["underused_count"] == 9
    assert body["attention"]["higher_workload_count"] == 3
    assert len(body["recent_weekly"]) == 6

    population = client.get(
        "/api/v1/analytics/population", params={"date": "2026-03-31"}
    ).json()
    kennel = client.get("/api/v1/kennel-map", params={"date": "2026-03-31"}).json()
    entry = client.get("/api/v1/daily-entry/2026-03-31").json()
    attention = client.get(
        "/api/v1/analytics/overview",
        params={"from": "2026-03-18", "to": "2026-03-31"},
    ).json()
    assert body["population"]["active_dogs"] == population["headline"]["active_dogs"]
    assert (
        body["population"]["unavailable_dogs"] == kennel["summary"]["unavailable_dogs"]
    )
    assert body["actual"]["dog_km"] == entry["summary"]["total_dog_km"]
    assert body["attention"]["underused_count"] == len(attention["underused"])


def test_dashboard_reflects_plan_and_saved_team_state(client: TestClient) -> None:
    participant_ids = dog_ids("Atlas", "Daisy", "Freya", "Kenzo")
    created = client.post(
        "/api/v1/daily-plans/2026-03-29/activities",
        json={
            "activity_type": "training",
            "start_time": "08:30:00",
            "title": "Forest Loop",
            "distance_km": 10,
            "notes": "A compact dashboard plan note.",
            "participant_ids": participant_ids,
            "expected_revision": None,
        },
    )
    assert created.status_code == 200, created.text
    plan = created.json()
    activity = plan["activities"][0]
    base = f"/api/v1/daily-plans/2026-03-29/activities/{activity['id']}"
    generated = client.post(
        f"{base}/teams/generate", json={"team_count": 1, "team_size": 4}
    )
    assert generated.status_code == 200, generated.text
    preview = generated.json()
    teams = [
        {
            "sequence": team["sequence"],
            "display_label": team["display_label"],
            "team_size": team["team_size"],
            "slots": [
                {
                    "dog_id": slot["dog_id"],
                    "pair_index": slot["pair_index"],
                    "side": slot["side"],
                    "harness_role": slot["harness_role"],
                    "position_order": slot["position_order"],
                }
                for slot in team["slots"]
            ],
        }
        for team in preview["teams"]
    ]
    saved = client.put(
        f"{base}/teams",
        json={
            "expected_revision": plan["revision"],
            "replace_existing": False,
            "teams": teams,
        },
    )
    assert saved.status_code == 200, saved.text

    body = client.get("/api/v1/dashboard", params={"date": "2026-03-29"}).json()
    assert body["plan"]["exists"] is True
    assert body["plan"]["activities_count"] == 1
    assert body["plan"]["planned_dogs"] == 4
    assert body["plan"]["planned_dog_km"] == 40
    assert body["plan"]["training_with_saved_teams"] == 1
    assert body["plan"]["training_without_saved_teams"] == 0
    assert body["plan"]["training"][0]["actual_status"] == "not_recorded"


@pytest.mark.parametrize("selected_date", ["2025-11-30", "2026-04-01"])
def test_dashboard_rejects_dates_outside_demo_season(
    client: TestClient, selected_date: str
) -> None:
    response = client.get("/api/v1/dashboard", params={"date": selected_date})
    assert response.status_code == 422


def test_dashboard_query_count_is_bounded() -> None:
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
            dashboard = DashboardService(
                session, DemoClock.from_settings(get_settings())
            ).read(date(2026, 3, 31))
            assert dashboard.actual.dog_km == 120
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    assert len(statements) <= 45
