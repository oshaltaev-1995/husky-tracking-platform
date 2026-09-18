from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.main import app
from app.models import DailyPlan, DemoWorkspace, DemoWorkspaceDay, Dog, WorkSession
from app.services.demo_workspace_service import (
    DemoWorkspaceService,
    cleanup_expired_workspaces,
    create_workspace,
)

BASELINE_CHECKSUM = "2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2"


@pytest.fixture(autouse=True)
def canonical_demo_world() -> Iterator[None]:
    with SessionLocal.begin() as session:
        reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
    yield
    app.dependency_overrides.clear()


def test_public_privacy_does_not_create_demo_cookie() -> None:
    response = TestClient(app).get("/api/v1/public/privacy")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert response.json()["demo_workspace_ttl_hours"] == 24


def test_demo_cookie_is_opaque_scoped_and_hardened() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/demo/session")
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1" in cookie
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    token = client.cookies.get("ht_demo_session")
    assert token is not None and len(token) >= 40
    with SessionLocal() as session:
        workspace = session.scalar(select(DemoWorkspace))
        assert workspace is not None
        assert workspace.token_hash != token
        assert len(workspace.token_hash) == 64


def test_production_cookie_is_secure() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_base_url="https://huskytracking.com",
        database_url="postgresql+psycopg://app:strong@db:5432/husky_tracking",
        cors_origins=["https://huskytracking.com"],
        allowed_hosts=["huskytracking.com"],
        demo_cookie_secure=True,
        demo_origin_check_enabled=True,
        demo_session_secret="a-strong-production-session-secret-12345",
        privacy_controller_name="Example controller",
        privacy_contact_email="privacy@example.com",
        privacy_controller_country="Example EEA country",
        privacy_hosting_region="Example EEA region",
        contact_delivery_mode="disabled",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    response = TestClient(app).get("/api/v1/demo/session")
    assert "Secure" in response.headers["set-cookie"]


def test_two_clients_are_isolated_and_first_write_materializes_date() -> None:
    first = TestClient(app)
    second = TestClient(app)
    first.get("/api/v1/demo/session")
    second.get("/api/v1/demo/session")

    updated = first.put(
        "/api/v1/daily-plans/2026-03-31",
        json={"notes": "First browser only", "expected_revision": None},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "First browser only"
    other = second.get("/api/v1/daily-plans/2026-03-31")
    assert other.status_code == 200
    assert other.json()["exists"] is False

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DemoWorkspace)) == 2
        assert session.scalar(select(func.count()).select_from(DemoWorkspaceDay)) == 1
        baseline_sessions = session.scalar(
            select(func.count())
            .select_from(WorkSession)
            .where(
                WorkSession.demo_workspace_id.is_(None),
                WorkSession.work_date == datetime(2026, 3, 31).date(),
            )
        )
        copied_sessions = session.scalar(
            select(func.count())
            .select_from(WorkSession)
            .where(WorkSession.demo_workspace_id.is_not(None))
        )
        assert copied_sessions == baseline_sessions
        assert semantic_checksum(session) == BASELINE_CHECKSUM


def test_workspace_reset_is_scoped_and_returns_to_baseline_view() -> None:
    first = TestClient(app)
    second = TestClient(app)
    for client, note in ((first, "first"), (second, "second")):
        client.put(
            "/api/v1/daily-plans/2026-03-31",
            json={"notes": note, "expected_revision": None},
        )

    reset = first.post("/api/v1/demo/reset")
    assert reset.status_code == 200
    assert first.get("/api/v1/daily-plans/2026-03-31").json()["exists"] is False
    assert second.get("/api/v1/daily-plans/2026-03-31").json()["notes"] == "second"
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DailyPlan)) == 1
        assert semantic_checksum(session) == BASELINE_CHECKSUM


def test_actual_and_analytics_use_workspace_overlay_without_double_counting() -> None:
    first = TestClient(app)
    second = TestClient(app)
    with SessionLocal() as session:
        atlas = session.scalar(select(Dog.public_id).where(Dog.name == "Atlas"))
    assert atlas is not None
    before = second.get(
        "/api/v1/analytics/overview",
        params={"from": "2025-12-01", "to": "2026-03-31"},
    ).json()["summary"]
    created = first.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json={
            "distance_km": 5,
            "start_time": "08:00:00",
            "label": "Private test run",
            "note": None,
            "participants": [{"dog_id": str(atlas)}],
        },
    )
    assert created.status_code == 200, created.text
    first_summary = first.get(
        "/api/v1/analytics/overview",
        params={"from": "2025-12-01", "to": "2026-03-31"},
    ).json()["summary"]
    second_summary = second.get(
        "/api/v1/analytics/overview",
        params={"from": "2025-12-01", "to": "2026-03-31"},
    ).json()["summary"]
    assert first_summary["sessions"] == before["sessions"] + 1
    assert first_summary["dog_starts"] == before["dog_starts"] + 1
    assert first_summary["dog_km"] == before["dog_km"] + 5
    assert second_summary == before
    assert len(first.get("/api/v1/daily-entry/2026-03-29").json()["sessions"]) == 1
    assert second.get("/api/v1/daily-entry/2026-03-29").json()["sessions"] == []


def test_saved_teams_are_visible_only_in_own_workspace() -> None:
    first = TestClient(app)
    second = TestClient(app)
    names = ["Atlas", "Daisy", "Freya", "Kenzo"]
    with SessionLocal() as session:
        rows = session.execute(
            select(Dog.name, Dog.public_id).where(Dog.name.in_(names))
        )
        ids = {name: str(public_id) for name, public_id in rows}
    plan = first.post(
        "/api/v1/daily-plans/2026-03-31/activities",
        json={
            "activity_type": "training",
            "start_time": "09:00:00",
            "title": "Private lineup",
            "distance_km": 5,
            "notes": None,
            "participant_ids": [ids[name] for name in names],
            "expected_revision": None,
        },
    ).json()
    activity_id = plan["activities"][0]["id"]
    base = f"/api/v1/daily-plans/2026-03-31/activities/{activity_id}"
    generated = first.post(
        f"{base}/teams/generate", json={"team_count": 1, "team_size": 4}
    )
    assert generated.status_code == 200, generated.text
    teams = generated.json()["teams"]
    saved = first.put(
        f"{base}/teams",
        json={
            "expected_revision": plan["revision"],
            "replace_existing": False,
            "teams": [
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
                for team in teams
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert len(first.get(f"{base}/team-builder").json()["saved_teams"]) == 1
    assert second.get(f"{base}/team-builder").status_code == 404


def test_editing_seeded_actual_changes_only_own_dashboard_and_not_baseline() -> None:
    first = TestClient(app)
    second = TestClient(app)
    work_date = "2025-12-01"
    baseline_day = second.get(f"/api/v1/daily-entry/{work_date}").json()
    target = baseline_day["sessions"][0]
    new_distance = 10 if target["distance_km"] == 5 else 5
    participants = [
        {
            "dog_id": row["dog_id"],
            "assigned_role": row["assigned_role"],
            "actual_team_sequence": row["actual_team_sequence"],
            "pair_index": row["pair_index"],
            "side": row["side"],
            "position_order": row["position_order"],
        }
        for row in target["participants"]
    ]
    changed = first.patch(
        f"/api/v1/daily-entry/{work_date}/sessions/{target['id']}",
        json={
            "distance_km": new_distance,
            "start_time": target["start_time"],
            "label": target["label"],
            "note": "Private correction",
            "participants": participants,
            "expected_revision": target["revision"],
        },
    )
    assert changed.status_code == 200, changed.text
    first_session = next(
        item for item in changed.json()["sessions"] if item["id"] == target["id"]
    )
    second_session = next(
        item
        for item in second.get(f"/api/v1/daily-entry/{work_date}").json()["sessions"]
        if item["id"] == target["id"]
    )
    assert first_session["distance_km"] == new_distance
    assert second_session["distance_km"] == target["distance_km"]

    first_dashboard = first.get("/api/v1/dashboard", params={"date": work_date}).json()
    second_dashboard = second.get(
        "/api/v1/dashboard", params={"date": work_date}
    ).json()
    delta = (new_distance - target["distance_km"]) * len(participants)
    assert (
        first_dashboard["actual"]["dog_km"]
        == second_dashboard["actual"]["dog_km"] + delta
    )
    with SessionLocal() as session:
        baseline = session.scalar(
            select(WorkSession).where(
                WorkSession.demo_workspace_id.is_(None),
                WorkSession.public_id == target["id"],
            )
        )
        assert baseline is not None
        assert baseline.distance_km == target["distance_km"]


def test_tampered_token_cannot_resolve_existing_workspace() -> None:
    client = TestClient(app)
    first = client.get("/api/v1/demo/session")
    assert first.status_code == 200
    client.cookies.set("ht_demo_session", "tampered-token-that-is-not-valid")
    replacement = client.get("/api/v1/demo/session")
    assert replacement.status_code == 200
    assert replacement.json()["created"] is True
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DemoWorkspace)) == 2


def test_concurrent_first_materialization_creates_one_workspace_day() -> None:
    with SessionLocal.begin() as session:
        workspace_id = create_workspace(
            session, 24, get_settings().demo_session_secret
        ).workspace.id

    def materialize() -> None:
        with SessionLocal.begin() as session:
            DemoWorkspaceService(session, workspace_id).materialize_date(
                datetime(2026, 3, 31).date()
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: materialize(), range(2)))

    with SessionLocal() as session:
        days = session.scalar(
            select(func.count())
            .select_from(DemoWorkspaceDay)
            .where(DemoWorkspaceDay.workspace_id == workspace_id)
        )
        assert days == 1


def test_expired_cookie_gets_fresh_workspace_and_cleanup_is_cascading() -> None:
    client = TestClient(app)
    initial = client.get("/api/v1/demo/session")
    assert initial.json()["created"] is True
    assert (
        client.put(
            "/api/v1/daily-plans/2026-03-31",
            json={"notes": "expires", "expected_revision": None},
        ).status_code
        == 200
    )
    with SessionLocal.begin() as session:
        workspace = session.scalar(select(DemoWorkspace))
        assert workspace is not None
        workspace.expires_at = datetime.now(UTC) - timedelta(minutes=1)

    renewed = client.get("/api/v1/demo/session")
    assert renewed.status_code == 200
    assert renewed.json()["created"] is True
    assert renewed.json()["replaced_expired"] is True
    assert renewed.headers["x-demo-session-state"] == "replaced-expired"
    assert client.get("/api/v1/daily-plans/2026-03-31").json()["exists"] is False
    with SessionLocal.begin() as session:
        assert cleanup_expired_workspaces(session) == 1
        assert cleanup_expired_workspaces(session) == 0
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DemoWorkspace)) == 1
