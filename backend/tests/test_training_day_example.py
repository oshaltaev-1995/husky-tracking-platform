"""Training Day acceptance on a positively identified disposable PostgreSQL only."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier, Event, Lock
from time import monotonic
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.catalog import EXPECTED_SEMANTIC_CHECKSUM
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.main import app
from app.models import (
    DailyPlan,
    DemoWorkspace,
    DemoWorkspaceDay,
    Dog,
    DogAvailabilityPeriod,
    DogRelationshipConstraint,
    DogRoleCapability,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)
from app.schemas.daily_entry import ActualSessionCreate
from app.schemas.training_day_example import TrainingDayApply
from app.services.daily_entry_service import DailyEntryService
from app.services.daily_plan_service import DailyPlanError, DailyPlanService
from app.services.demo_workspace_service import DemoWorkspaceService, resolve_workspace
from app.services.training_day_example_service import TrainingDayExampleService

DAY = "2026-03-29"
DAY_DATE = date(2026, 3, 29)
BASE = "/api/v1/training-day-example"


@pytest.fixture(autouse=True)
def disposable_world() -> Iterator[None]:
    if os.environ.get("P13F_DISPOSABLE_DB_CONFIRMED") != "1":
        pytest.skip("P13F requires an explicitly confirmed disposable PostgreSQL")
    assert engine.url.get_backend_name() == "postgresql"
    assert engine.url.host == "127.0.0.1"
    assert engine.url.database == "husky_tracking"
    with SessionLocal.begin() as session:
        reset_demo_world(session, clock(), require_enabled=False)
    yield
    app.dependency_overrides.clear()


def clock() -> DemoClock:
    return DemoClock.from_settings(get_settings())


def client(cookie: str | None = None) -> TestClient:
    visitor = TestClient(app)
    if cookie is None:
        assert visitor.get("/api/v1/demo/session").status_code == 200
    else:
        visitor.cookies.set("ht_demo_session", cookie)
    return visitor


def workspace_id(visitor: TestClient) -> int:
    with SessionLocal() as session:
        workspace = resolve_workspace(
            session,
            visitor.cookies.get("ht_demo_session"),
            get_settings().demo_session_secret,
        )
        assert workspace is not None
        return workspace.id


def proposal(visitor: TestClient) -> dict[str, Any]:
    response = visitor.get(BASE)
    assert response.status_code == 200, response.text
    return response.json()


def apply_payload(review: dict[str, Any]) -> dict[str, Any]:
    assert review["available"] is True, review["unavailable_reason"]
    return {
        "date": review["date"],
        "preset_version": review["preset_version"],
        "participant_ids": [dog["id"] for dog in review["participants"]],
        "precondition": review["precondition"],
    }


def graph_counts() -> dict[str, int]:
    with SessionLocal() as session:
        counts = {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                DailyPlan,
                PlannedActivity,
                PlannedActivityParticipant,
                PlannedTeam,
                PlannedTeamSlot,
                DemoWorkspaceDay,
            )
        }
        counts["workspace_actuals"] = session.scalar(
            select(func.count())
            .select_from(WorkSession)
            .where(WorkSession.demo_workspace_id.is_not(None))
        )
    return counts


def assert_baseline() -> None:
    with SessionLocal() as session:
        assert semantic_checksum(session) == EXPECTED_SEMANTIC_CHECKSUM
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkSession)
                .where(WorkSession.demo_workspace_id.is_(None))
            )
            == 140
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkParticipation)
                .join(WorkSession)
                .where(WorkSession.demo_workspace_id.is_(None))
            )
            == 1120
        )


def overview(visitor: TestClient) -> dict[str, Any]:
    response = visitor.get(
        "/api/v1/analytics/overview", params={"from": "2025-12-01", "to": "2026-03-31"}
    )
    assert response.status_code == 200
    return response.json()["summary"]


def actual_payload(dog_id: str) -> dict[str, Any]:
    return {
        "distance_km": 5,
        "start_time": "08:00:00",
        "label": "Isolated QA actual",
        "participants": [{"dog_id": dog_id}],
    }


def test_preview_is_deterministic_read_only_and_describes_repeated_participation() -> (
    None
):
    visitor = client()
    before = graph_counts()
    first = proposal(visitor)
    assert proposal(visitor) == first
    assert first["date"] == DAY and first["preset_version"] == "training-day-v1"
    assert first["available"] is True and first["precondition"]
    assert (
        first["unique_dogs"],
        first["planned_participations"],
        first["planned_dog_km"],
        first["planned_km_per_dog"],
    ) == (16, 64, 320, 20)
    assert len(first["participants"]) == 16
    assert len({dog["id"] for dog in first["participants"]}) == 16
    assert [activity["start_time"][:5] for activity in first["activities"]] == [
        "09:00",
        "10:30",
        "12:30",
        "14:00",
    ]
    assert [activity["suggested_end_time"][:5] for activity in first["activities"]] == [
        "10:00",
        "11:30",
        "13:30",
        "15:00",
    ]
    assert all(activity["distance_km"] == 5 for activity in first["activities"])
    assert graph_counts() == before
    assert all(value == 0 for value in before.values())
    assert_baseline()


def test_atomic_apply_creates_four_ordinary_activities_only_in_own_workspace() -> None:
    first, other = client(), client()
    before = overview(first)
    review = proposal(first)
    saved = first.post(f"{BASE}/apply", json=apply_payload(review))
    assert saved.status_code == 200, saved.text
    plan = saved.json()
    assert plan["selected_date"] == DAY and len(plan["activities"]) == 4
    ids = {dog["id"] for dog in review["participants"]}
    for number, activity in enumerate(plan["activities"], 1):
        assert (
            activity["sequence"] == number and activity["activity_type"] == "training"
        )
        assert activity["distance_km"] == 5
        assert activity["start_time"] == review["activities"][number - 1]["start_time"]
        assert activity["title"] == review["activities"][number - 1]["title"]
        assert {dog["id"] for dog in activity["participants"]} == ids
        assert activity["team_count"] == 0 and activity["arranged_dog_count"] == 0
    assert first.get(f"/api/v1/daily-plans/{DAY}").json() == plan
    assert other.get(f"/api/v1/daily-plans/{DAY}").json()["exists"] is False
    assert first.get(f"/api/v1/daily-entry/{DAY}").json()["sessions"] == []
    assert overview(first) == before == overview(other)
    assert graph_counts()["planned_activity_participants"] == 64
    eligible = first.get(
        f"/api/v1/daily-plans/{DAY}/eligible-dogs",
        params={
            "activity_type": "training",
            "distance_km": 5,
        },
    ).json()["dogs"]
    assert all(dog["planned_training_km"] == 20 for dog in eligible if dog["id"] in ids)
    assert_baseline()


@pytest.mark.parametrize("failure_number", [3, 4])
def test_late_activity_validation_rolls_back_entire_graph(
    monkeypatch: pytest.MonkeyPatch, failure_number: int
) -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    original = DailyPlanService.create_activity
    calls = 0

    def late_failure(self: DailyPlanService, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        result = original(self, *args, **kwargs)
        calls += 1
        if calls == failure_number:
            raise DailyPlanError(
                "qa_late_validation", "Controlled late validation failure."
            )
        return result

    monkeypatch.setattr(DailyPlanService, "create_activity", late_failure)
    response = visitor.post(f"{BASE}/apply", json=payload)
    assert response.status_code == 422, response.text
    assert calls == failure_number
    assert all(value == 0 for value in graph_counts().values())
    assert_baseline()


@pytest.mark.parametrize(
    "occupied", ["notes", "activity", "workspace_actual", "canonical_actual"]
)
def test_occupied_day_is_never_overwritten(occupied: str) -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    dog = payload["participant_ids"][0]
    if occupied == "notes":
        assert (
            visitor.put(
                f"/api/v1/daily-plans/{DAY}",
                json={
                    "notes": "Keep this note",
                    "expected_revision": None,
                },
            ).status_code
            == 200
        )
    elif occupied == "activity":
        assert (
            visitor.post(
                f"/api/v1/daily-plans/{DAY}/activities",
                json={
                    "activity_type": "training",
                    "title": "Keep manual activity",
                    "distance_km": 5,
                    "participant_ids": [dog],
                    "expected_revision": None,
                },
            ).status_code
            == 200
        )
    elif occupied == "workspace_actual":
        assert (
            visitor.post(
                f"/api/v1/daily-entry/{DAY}/sessions", json=actual_payload(dog)
            ).status_code
            == 200
        )
    else:
        with SessionLocal.begin() as session:
            DailyEntryService(session, clock()).create_manual(
                DAY_DATE, ActualSessionCreate.model_validate(actual_payload(dog))
            )
    before_plan = visitor.get(f"/api/v1/daily-plans/{DAY}").json()
    before_actual = visitor.get(f"/api/v1/daily-entry/{DAY}").json()
    counts = graph_counts()
    unavailable = proposal(visitor)
    assert unavailable["available"] is False and unavailable["precondition"] is None
    assert unavailable["unavailable_reason"]
    rejected = visitor.post(f"{BASE}/apply", json=payload)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "training_day_occupied"
    assert visitor.get(f"/api/v1/daily-plans/{DAY}").json() == before_plan
    assert visitor.get(f"/api/v1/daily-entry/{DAY}").json() == before_actual
    assert graph_counts() == counts


def test_empty_reset_generation_and_cross_cookie_preconditions() -> None:
    visitor, other = client(), client()
    payload = apply_payload(proposal(visitor))
    assert other.post(f"{BASE}/apply", json=payload).status_code == 409
    anonymous = TestClient(app)
    denied = anonymous.post(f"{BASE}/apply", json=payload)
    assert denied.status_code == 401 and "set-cookie" not in denied.headers
    assert visitor.post("/api/v1/demo/reset").status_code == 200
    denied = visitor.post(f"{BASE}/apply", json=payload)
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "training_day_changed"
    fresh = apply_payload(proposal(visitor))
    assert fresh["precondition"] != payload["precondition"]
    assert all(value == 0 for value in graph_counts().values())
    assert_baseline()


def test_reviewed_date_version_and_participant_payload_cannot_be_substituted() -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    with SessionLocal() as session:
        outside = session.scalar(
            select(Dog.public_id).where(
                Dog.public_id.not_in(
                    [UUID(value) for value in payload["participant_ids"]]
                )
            )
        )
    assert outside is not None
    modified = [str(outside), *payload["participant_ids"][1:]]
    for change in (
        {"date": "2026-03-28"},
        {"preset_version": "unreviewed-version"},
        {"participant_ids": modified},
        {"precondition": "invalid-review-token"},
    ):
        response = visitor.post(f"{BASE}/apply", json={**payload, **change})
        assert response.status_code in {409, 422}, response.text
    for change in (
        {"workspace_id": workspace_id(visitor)},
        {"participant_ids": []},
        {"participant_ids": [payload["participant_ids"][0]] * 16},
    ):
        assert (
            visitor.post(f"{BASE}/apply", json={**payload, **change}).status_code == 422
        )
    assert all(value == 0 for value in graph_counts().values())


def test_expired_cookie_cannot_replace_session_during_apply() -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    identity = workspace_id(visitor)
    with SessionLocal.begin() as session:
        workspace = session.get(DemoWorkspace, identity)
        assert workspace is not None
        workspace.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    response = visitor.post(f"{BASE}/apply", json=payload)
    assert response.status_code == 401 and "set-cookie" not in response.headers
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DemoWorkspace)) == 1
    assert all(value == 0 for value in graph_counts().values())


def test_effective_eligibility_change_rejects_review_without_silent_substitution() -> (
    None
):
    visitor = client()
    payload = apply_payload(proposal(visitor))
    with SessionLocal.begin() as session:
        dog = session.scalar(
            select(Dog).where(Dog.public_id == UUID(payload["participant_ids"][0]))
        )
        assert dog is not None
        periods = list(
            session.scalars(
                select(DogAvailabilityPeriod).where(
                    DogAvailabilityPeriod.dog_id == dog.id,
                    DogAvailabilityPeriod.valid_from <= DAY_DATE,
                )
            )
        )
        current = next(
            item
            for item in periods
            if item.valid_to is None or item.valid_to > DAY_DATE
        )
        current.availability_state = "injured"
    response = visitor.post(f"{BASE}/apply", json=payload)
    assert response.status_code == 409, response.text
    assert all(value == 0 for value in graph_counts().values())


@pytest.mark.parametrize("shortage", ["lead", "eligible"])
def test_shortage_is_explained_without_persisting_a_partial_example(
    shortage: str,
) -> None:
    visitor = client()
    with SessionLocal.begin() as session:
        if shortage == "lead":
            for capability in session.scalars(
                select(DogRoleCapability).where(DogRoleCapability.role == "lead")
            ):
                session.delete(capability)
        else:
            for period in session.scalars(select(DogAvailabilityPeriod)):
                period.availability_state = "injured"
    review = proposal(visitor)
    assert review["available"] is False and review["unavailable_reason"]
    assert review["precondition"] is None
    assert all(value == 0 for value in graph_counts().values())


def test_existing_same_origin_guard_protects_the_example_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_origin_check_enabled", True)
    visitor = client()
    payload = apply_payload(proposal(visitor))
    for headers in ({}, {"Origin": "https://other.invalid"}):
        assert (
            visitor.post(f"{BASE}/apply", json=payload, headers=headers).status_code
            == 403
        )
    assert all(value == 0 for value in graph_counts().values())
    accepted = visitor.post(
        f"{BASE}/apply", json=payload, headers={"Origin": settings.public_base_url}
    )
    assert accepted.status_code == 200, accepted.text
    assert_baseline()


def test_reference_date_housing_move_does_not_leak_into_historical_training_pool() -> (
    None
):
    visitor = client()
    before = proposal(visitor)
    dog = before["participants"][0]
    snapshot = visitor.get("/api/v1/kennel-map").json()
    moved = visitor.post(
        "/api/v1/kennel-map/moves",
        json={
            "effective_date": "2026-03-31",
            "precondition": snapshot["housing_edit"]["precondition"],
            "moves": [{"dog_id": dog["id"], "destination_code": "PUPPY-A"}],
        },
    )
    assert moved.status_code == 200, moved.text
    after = proposal(visitor)
    assert after["participants"] == before["participants"]
    assert (
        visitor.get(f"/api/v1/dogs/{dog['id']}").json()["state"]["housing"]["code"]
        == "PUPPY-A"
    )
    assert visitor.post(f"{BASE}/apply", json=apply_payload(before)).status_code == 409
    assert visitor.post(f"{BASE}/apply", json=apply_payload(after)).status_code == 200
    assert_baseline()


def test_existing_planned_30_km_guardrail_remains_enforced_after_example() -> None:
    visitor = client()
    response = visitor.post(f"{BASE}/apply", json=apply_payload(proposal(visitor)))
    assert response.status_code == 200
    plan = response.json()
    dog = plan["activities"][0]["participants"][0]["id"]
    for number in range(2):
        saved = visitor.post(
            f"/api/v1/daily-plans/{DAY}/activities",
            json={
                "activity_type": "training",
                "title": f"Additional 5 km loop {number + 1}",
                "distance_km": 5,
                "participant_ids": [dog],
                "expected_revision": plan["revision"],
            },
        )
        assert saved.status_code == 200, saved.text
        plan = saved.json()
    rejected = visitor.post(
        f"/api/v1/daily-plans/{DAY}/activities",
        json={
            "activity_type": "training",
            "title": "Would exceed 30 km",
            "distance_km": 5,
            "participant_ids": [dog],
            "expected_revision": plan["revision"],
        },
    )
    assert rejected.status_code == 422
    assert visitor.get(f"/api/v1/daily-plans/{DAY}").json() == plan
    assert len(plan["activities"]) == 6
    assert_baseline()


class WorkspaceLockAttempt:
    """Observe real PostgreSQL lock waits; do not replace the writer query."""

    def __init__(self) -> None:
        self.attempted = Event()
        self.pids: set[int] = set()
        self.guard = Lock()

    def __call__(self, *args: Any) -> None:
        if "FOR UPDATE" in args[2] and "demo_workspaces" in args[2]:
            with self.guard:
                self.pids.add(args[0].connection.driver_connection.info.backend_pid)
            self.attempted.set()

    def assert_blocked(self, count: int = 1) -> None:
        assert self.attempted.wait(5), "no real workspace lock attempted"
        deadline = monotonic() + 5
        with engine.connect() as observer:
            while monotonic() < deadline:
                with self.guard:
                    pids = list(self.pids)
                blocked = [
                    pid
                    for pid in pids
                    if observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                        {"pid": pid},
                    )
                ]
                if len(blocked) >= count:
                    return
                Event().wait(0.01)
        pytest.fail("PostgreSQL did not confirm the expected blocked writers")


def test_two_real_concurrent_apply_transactions_create_only_one_example() -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    cookie = visitor.cookies.get("ht_demo_session")
    assert cookie is not None
    start = Barrier(2)

    def apply() -> int:
        writer = client(cookie)
        start.wait(timeout=5)
        return writer.post(f"{BASE}/apply", json=payload).status_code

    attempt = WorkspaceLockAttempt()
    with ThreadPoolExecutor(max_workers=2) as pool:
        with SessionLocal.begin() as holder:
            holder.scalar(
                select(DemoWorkspace)
                .where(DemoWorkspace.id == workspace_id(visitor))
                .with_for_update()
            )
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                futures = [pool.submit(apply) for _ in range(2)]
                attempt.assert_blocked(2)
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert sorted(future.result(timeout=20) for future in futures) == [200, 409]
    assert len(visitor.get(f"/api/v1/daily-plans/{DAY}").json()["activities"]) == 4
    assert graph_counts()["planned_activity_participants"] == 64
    assert_baseline()


@pytest.mark.parametrize("writer", ["notes", "actual"])
def test_apply_wins_real_lock_race_and_pending_ordinary_writer_fails_safely(
    writer: str,
) -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    identity = workspace_id(visitor)
    attempt = WorkspaceLockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as holder:
            expected = TrainingDayExampleService(holder, clock(), identity).apply(
                TrainingDayApply.model_validate(payload)
            )
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                if writer == "notes":
                    future = pool.submit(
                        visitor.put,
                        f"/api/v1/daily-plans/{DAY}",
                        json={
                            "notes": "Pending ordinary note",
                            "expected_revision": None,
                        },
                    )
                else:
                    future = pool.submit(
                        visitor.post,
                        f"/api/v1/daily-entry/{DAY}/sessions",
                        json=actual_payload(payload["participant_ids"][0]),
                    )
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=20).status_code == 409
    assert visitor.get(f"/api/v1/daily-plans/{DAY}").json() == expected.model_dump(
        mode="json"
    )
    assert visitor.get(f"/api/v1/daily-entry/{DAY}").json()["sessions"] == []
    assert_baseline()


@pytest.mark.parametrize("writer", ["notes", "actual"])
def test_ordinary_writer_wins_real_lock_race_and_apply_preserves_the_day(
    writer: str,
) -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    identity = workspace_id(visitor)
    attempt = WorkspaceLockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as holder:
            if writer == "notes":
                DailyPlanService(holder, clock(), identity).update_notes(
                    DAY_DATE, "Keep winning note", None
                )
            else:
                DailyEntryService(holder, clock(), identity).create_manual(
                    DAY_DATE,
                    ActualSessionCreate.model_validate(
                        actual_payload(payload["participant_ids"][0])
                    ),
                )
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(visitor.post, f"{BASE}/apply", json=payload)
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=20).status_code == 409
    day = visitor.get(f"/api/v1/daily-entry/{DAY}").json()
    plan = visitor.get(f"/api/v1/daily-plans/{DAY}").json()
    assert plan["activities"] == []
    assert (
        (plan["notes"] == "Keep winning note")
        if writer == "notes"
        else len(day["sessions"]) == 1
    )
    assert_baseline()


def test_expiry_after_lock_wait_is_rechecked_before_apply() -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    identity = workspace_id(visitor)
    attempt = WorkspaceLockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as holder:
            workspace = holder.scalar(
                select(DemoWorkspace)
                .where(DemoWorkspace.id == identity)
                .with_for_update()
            )
            assert workspace is not None
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(visitor.post, f"{BASE}/apply", json=payload)
                attempt.assert_blocked()
                workspace.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=20).status_code == 401
    assert all(value == 0 for value in graph_counts().values())


def test_empty_reset_wins_real_lock_race_and_stales_pending_apply() -> None:
    visitor = client()
    payload = apply_payload(proposal(visitor))
    identity = workspace_id(visitor)
    attempt = WorkspaceLockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as holder:
            DemoWorkspaceService(holder, identity).reset()
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(visitor.post, f"{BASE}/apply", json=payload)
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=20).status_code == 409
    assert all(value == 0 for value in graph_counts().values())
    assert_baseline()


def test_saved_two_team_lineup_actual_overlay_and_reset_follow_existing_truth() -> None:
    first, other = client(), client()
    before = overview(first)
    review = proposal(first)
    plan_response = first.post(f"{BASE}/apply", json=apply_payload(review))
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    activity = plan["activities"][0]
    path = f"/api/v1/daily-plans/{DAY}/activities/{activity['id']}"
    generated = first.post(
        f"{path}/teams/generate", json={"team_count": 2, "team_size": 8}
    )
    assert generated.status_code == 200, generated.text
    teams = generated.json()["teams"]
    assert len(teams) == 2 and graph_counts()["planned_teams"] == 0
    capabilities = {
        dog["id"]: set(dog["capabilities"]) for dog in review["participants"]
    }
    with SessionLocal() as session:
        names = {dog.id: str(dog.public_id) for dog in session.scalars(select(Dog))}
        conflicts = {
            frozenset((names[row.dog_a_id], names[row.dog_b_id]))
            for row in session.scalars(
                select(DogRelationshipConstraint).where(
                    DogRelationshipConstraint.relationship_kind == "hard_conflict"
                )
            )
        }
    for team in teams:
        pairs: dict[int, set[str]] = {}
        for slot in team["slots"]:
            assert slot["harness_role"] in capabilities[slot["dog_id"]]
            pairs.setdefault(slot["pair_index"], set()).add(slot["dog_id"])
        assert all(frozenset(pair) not in conflicts for pair in pairs.values())
    saved = first.put(
        f"{path}/teams",
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
                            key: slot[key]
                            for key in (
                                "dog_id",
                                "pair_index",
                                "side",
                                "harness_role",
                                "position_order",
                            )
                        }
                        for slot in team["slots"]
                    ],
                }
                for team in teams
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    arranged = first.get(f"/api/v1/daily-plans/{DAY}").json()
    assert [row["team_count"] for row in arranged["activities"]] == [2, 0, 0, 0]
    assert overview(first) == before
    recorded = first.post(
        f"/api/v1/daily-entry/{DAY}/planned-activities/{activity['id']}/confirm"
    )
    assert recorded.status_code == 200, recorded.text
    actual = recorded.json()["sessions"]
    assert len(actual) == 1 and len(actual[0]["participants"]) == 16
    assert actual[0]["distance_km"] == 5
    assert {dog["dog_id"] for dog in actual[0]["participants"]} == {
        dog["id"] for dog in review["participants"]
    }
    assert {dog["actual_team_sequence"] for dog in actual[0]["participants"]} == {1, 2}
    assert all(
        row["actual_status"] == "not_recorded"
        for row in recorded.json()["planned_activities"][1:]
    )
    repeated = first.post(
        f"/api/v1/daily-entry/{DAY}/planned-activities/{activity['id']}/confirm"
    )
    # P7 intentionally treats the already-confirmed plan as an idempotent read.
    assert repeated.status_code == 200
    assert repeated.json() == recorded.json()
    after = overview(first)
    assert after["sessions"] == before["sessions"] + 1
    assert after["dog_starts"] == before["dog_starts"] + 16
    assert after["dog_km"] == before["dog_km"] + 80
    assert overview(other) == before
    dog = review["participants"][0]["id"]
    own_work = first.get(f"/api/v1/dogs/{dog}/work").json()["summary"]
    other_work = other.get(f"/api/v1/dogs/{dog}/work").json()["summary"]
    assert own_work["starts"] == other_work["starts"] + 1
    assert own_work["total_km"] == other_work["total_km"] + 5
    assert first.post("/api/v1/demo/reset").status_code == 200
    assert first.get(f"/api/v1/daily-plans/{DAY}").json()["exists"] is False
    assert first.get(f"/api/v1/daily-entry/{DAY}").json()["sessions"] == []
    assert overview(first) == before
    assert first.get(f"/api/v1/dogs/{dog}/work").json()["summary"] == other_work
    assert all(value == 0 for value in graph_counts().values())
    assert_baseline()
