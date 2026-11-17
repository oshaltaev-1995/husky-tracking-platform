from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier, Event, Lock
from time import monotonic
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.catalog import EXPECTED_SEMANTIC_CHECKSUM
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.demo.validation import DemoValidationError, validate_demo_world
from app.main import app
from app.models import (
    DailyPlan,
    DemoWorkspace,
    DemoWorkspaceDay,
    Dog,
    DogLifecyclePeriod,
    HousingAssignment,
    KennelLocation,
    WorkSession,
)
from app.services.demo_workspace_service import (
    DemoWorkspaceService,
    cleanup_expired_workspaces,
    resolve_workspace,
)

DATE = "2026-03-31"


@pytest.fixture(autouse=True)
def world() -> Iterator[None]:
    with SessionLocal.begin() as session:
        reset_demo_world(
            session, DemoClock.from_settings(get_settings()), require_enabled=False
        )
    yield


def client() -> TestClient:
    visitor = TestClient(app)
    assert visitor.get("/api/v1/demo/session").status_code == 200
    return visitor


def dog_id(name: str) -> str:
    with SessionLocal() as session:
        return str(session.scalar(select(Dog.public_id).where(Dog.name == name)))


def snapshot(visitor: TestClient, when: str = DATE) -> dict:
    response = visitor.get("/api/v1/kennel-map", params={"date": when})
    assert response.status_code == 200, response.text
    return response.json()


def homes(body: dict) -> dict[str, str]:
    return {
        resident["name"]: location["code"]
        for location in body["locations"]
        for resident in location["residents"]
    }


def payload(visitor: TestClient, *moves: tuple[str, str]) -> dict:
    return {
        "effective_date": DATE,
        "precondition": snapshot(visitor)["housing_edit"]["precondition"],
        "moves": [
            {"dog_id": dog_id(name), "destination_code": destination}
            for name, destination in moves
        ],
    }


def assert_baseline() -> None:
    with SessionLocal() as session:
        assert semantic_checksum(session) == EXPECTED_SEMANTIC_CHECKSUM
        validate_demo_world(session, DemoClock.from_settings(get_settings()))


def test_baseline_get_never_issues_cookie_even_for_invalid_or_expired_cookie() -> None:
    visitor = TestClient(app)
    for cookie in (None, "tampered-opaque-cookie-value"):
        if cookie:
            visitor.cookies.set("ht_demo_session", cookie)
        response = visitor.get("/api/v1/kennel-map")
        assert response.status_code == 200
        assert "set-cookie" not in response.headers
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["housing_edit"]["editable"] is False
        assert response.json()["housing_edit"]["precondition"] is None
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DemoWorkspace)) == 0


def test_occupied_over_capacity_cross_type_and_unavailable_moves_are_allowed() -> None:
    a, b = client(), client()
    baseline = snapshot(a)
    result = a.post(
        "/api/v1/kennel-map/moves",
        json=payload(
            a,
            ("Aurora", "PUPPY-A"),
            ("Fjord", "PUPPY-A"),
            ("Hazel", "PUPPY-A"),
            ("Cedar", "A1-01"),
            ("Orion", "A1-01"),
        ),
    )
    assert result.status_code == 200, result.text
    updated = result.json()
    puppy = next(loc for loc in updated["locations"] if loc["code"] == "PUPPY-A")
    assert puppy["capacity"] == 5 and len(puppy["residents"]) == 8
    assert {"Taro", "Tessa", "Theo", "Tindra", "Toast"} <= {
        dog["name"] for dog in puppy["residents"]
    }
    adult = next(loc for loc in updated["locations"] if loc["code"] == "A1-01")
    assert {"Atlas", "Cedar", "Orion"} == {dog["name"] for dog in adult["residents"]}
    assert (
        updated["housing_edit"]["revision"] == baseline["housing_edit"]["revision"] + 1
    )
    assert homes(snapshot(b)) == homes(baseline)
    assert homes(snapshot(a, "2026-03-29")) == homes(snapshot(b, "2026-03-29"))
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DailyPlan)) == 0
        assert session.scalar(select(func.count()).select_from(DemoWorkspaceDay)) == 0
        assert session.scalar(select(func.count()).select_from(WorkSession)) == 140
    assert_baseline()


def test_partial_invalid_batch_and_duplicates_leave_no_changes_or_revision() -> None:
    a = client()
    before = snapshot(a)
    invalid = payload(a, ("Aurora", "PUPPY-A"), ("Atlas", "no-such-location"))
    response = a.post("/api/v1/kennel-map/moves", json=invalid)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "housing_invalid_destination"
    assert snapshot(a) == before
    duplicate = payload(a, ("Atlas", "A2-01"), ("Atlas", "B2-01"))
    response = a.post("/api/v1/kennel-map/moves", json=duplicate)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "housing_duplicate_dog"
    assert snapshot(a) == before


def test_move_noop_repeat_baseline_return_and_stale_precondition() -> None:
    a = client()
    before = snapshot(a)
    noop = a.post("/api/v1/kennel-map/moves", json=payload(a, ("Atlas", "A1-01")))
    assert noop.status_code == 200 and noop.json() == before
    change = payload(a, ("Atlas", "B2-01"))
    moved = a.post("/api/v1/kennel-map/moves", json=change)
    assert moved.status_code == 200, moved.text
    assert homes(moved.json())["Atlas"] == "B2-01"
    stale = a.post("/api/v1/kennel-map/moves", json=change)
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "housing_changed"
    second = a.post("/api/v1/kennel-map/moves", json=payload(a, ("Atlas", "B1-01")))
    assert second.status_code == 200 and homes(second.json())["Atlas"] == "B1-01"
    returned = a.post("/api/v1/kennel-map/moves", json=payload(a, ("Atlas", "A1-01")))
    assert returned.status_code == 200
    assert homes(returned.json()) == homes(before)
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM demo_workspace_housing_overrides"
            ).scalar_one()
            == 0
        )
    assert_baseline()


def test_authorization_date_batch_bounds_and_cross_workspace_precondition() -> None:
    a, b = client(), client()
    change = payload(a, ("Atlas", "A2-01"))
    assert b.post("/api/v1/kennel-map/moves", json=change).status_code == 409
    anonymous = TestClient(app)
    response = anonymous.post("/api/v1/kennel-map/moves", json=change)
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    for when in ("2026-03-29", "2026-04-01"):
        assert (
            a.post(
                "/api/v1/kennel-map/moves", json={**change, "effective_date": when}
            ).status_code
            == 422
        )
    for moves in ([], change["moves"] * 61):
        assert (
            a.post(
                "/api/v1/kennel-map/moves", json={**change, "moves": moves}
            ).status_code
            == 422
        )
    assert (
        a.post(
            "/api/v1/kennel-map/moves", json={**change, "workspace_id": 123}
        ).status_code
        == 422
    )
    with SessionLocal.begin() as session:
        rows = list(session.scalars(select(DemoWorkspace)))
        for row in rows:
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    response = a.post("/api/v1/kennel-map/moves", json=change)
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert snapshot(a)["housing_edit"]["editable"] is False
    assert a.get("/api/v1/demo/session").status_code == 200
    assert a.post("/api/v1/kennel-map/moves", json=change).status_code == 409


def test_inactive_unborn_unknown_dog_or_inactive_location_fail_closed() -> None:
    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    with SessionLocal() as session:
        archived = str(
            session.scalar(
                select(Dog.public_id)
                .join(Dog.lifecycle_periods)
                .where(DogLifecyclePeriod.lifecycle_state == "archived")
            )
        )
    for identity in (archived, str(uuid4())):
        response = a.post(
            "/api/v1/kennel-map/moves",
            json={
                **change,
                "moves": [{"dog_id": identity, "destination_code": "A2-01"}],
            },
        )
        assert response.status_code == 422
    with SessionLocal.begin() as session:
        atlas = session.scalar(select(Dog).where(Dog.name == "Atlas"))
        assert atlas is not None
        atlas.birth_date = date(2026, 4, 1)
        atlas.neutered_on = None
    response = a.post("/api/v1/kennel-map/moves", json=change)
    assert response.status_code == 422
    with SessionLocal.begin() as session:
        atlas = session.scalar(select(Dog).where(Dog.name == "Atlas"))
        assert atlas is not None
        atlas.birth_date = date(2016, 2, 10)
        target = session.scalar(
            select(KennelLocation).where(KennelLocation.code == "A2-01")
        )
        assert target is not None
        target.is_active = False
    assert a.post("/api/v1/kennel-map/moves", json=change).status_code == 422


def test_reset_and_cleanup_invalidate_moves_preserve_other_workspace_and_checksum() -> (
    None
):
    a, b = client(), client()
    for visitor, destination in ((a, "A2-01"), (b, "B2-01")):
        assert (
            visitor.post(
                "/api/v1/kennel-map/moves",
                json=payload(visitor, ("Atlas", destination)),
            ).status_code
            == 200
        )
    stale = payload(a, ("Atlas", "PUPPY-A"))
    before_revision = snapshot(a)["housing_edit"]["revision"]
    assert a.post("/api/v1/demo/reset").status_code == 200
    assert snapshot(a)["housing_edit"]["revision"] == before_revision + 1
    assert homes(snapshot(a))["Atlas"] == "A1-01"
    assert homes(snapshot(b))["Atlas"] == "B2-01"
    assert a.post("/api/v1/kennel-map/moves", json=stale).status_code == 409
    empty_revision = snapshot(a)["housing_edit"]["revision"]
    assert a.post("/api/v1/demo/reset").status_code == 200
    assert snapshot(a)["housing_edit"]["revision"] == empty_revision + 1
    with SessionLocal.begin() as session:
        for row in session.scalars(select(DemoWorkspace)):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.flush()
        assert cleanup_expired_workspaces(session) == 2
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM demo_workspace_housing_overrides"
            ).scalar_one()
            == 0
        )
    assert_baseline()


def workspace_id(visitor: TestClient) -> int:
    with SessionLocal() as session:
        workspace = resolve_workspace(
            session,
            visitor.cookies.get("ht_demo_session"),
            get_settings().demo_session_secret,
        )
        assert workspace is not None
        return workspace.id


def test_reference_date_is_taken_from_demo_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import kennel_map

    settings = get_settings().model_copy(
        update={"demo_reference_date": date(2026, 1, 1)}
    )
    monkeypatch.setattr(kennel_map, "get_settings", lambda: settings)
    a = client()
    initial = snapshot(a, "2026-01-01")
    change = {
        "effective_date": "2026-01-01",
        "precondition": initial["housing_edit"]["precondition"],
        "moves": [{"dog_id": dog_id("Taro"), "destination_code": "A2-01"}],
    }
    assert a.post("/api/v1/kennel-map/moves", json=change).status_code == 422
    change["moves"] = [{"dog_id": dog_id("Atlas"), "destination_code": "A2-01"}]
    result = a.post("/api/v1/kennel-map/moves", json=change)
    assert result.status_code == 200, result.text
    assert homes(result.json())["Atlas"] == "A2-01"
    assert homes(snapshot(a, "2026-03-31"))["Atlas"] == "A1-01"


def test_same_origin_guard_and_precondition_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_origin_check_enabled", True)
    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    assert (
        a.post(
            "/api/v1/kennel-map/moves",
            json=change,
            headers={"Origin": "https://other.invalid"},
        ).status_code
        == 403
    )
    assert a.post("/api/v1/kennel-map/moves", json=change).status_code == 403
    assert (
        a.post(
            "/api/v1/kennel-map/moves",
            json={**change, "precondition": "h1." + "0" * 64},
            headers={"Origin": settings.public_base_url},
        ).status_code
        == 409
    )
    assert (
        a.post(
            "/api/v1/kennel-map/moves",
            json=change,
            headers={"Origin": settings.public_base_url},
        ).status_code
        == 200
    )


class LockAttempt:
    """Signal the real PostgreSQL FOR UPDATE attempt; never replace the query."""

    def __init__(self) -> None:
        self.attempted = Event()
        self.pids: set[int] = set()
        self.guard = Lock()

    def __call__(self, *args: Any) -> None:
        statement = args[2]
        if "FOR UPDATE" in statement and "demo_workspaces" in statement:
            with self.guard:
                self.pids.add(args[0].connection.driver_connection.info.backend_pid)
            self.attempted.set()

    def assert_blocked(self, count: int = 1) -> None:
        assert self.attempted.wait(5), "workspace row lock was not attempted"
        deadline = monotonic() + 5
        with engine.connect() as observer:
            while monotonic() < deadline:
                with self.guard:
                    pids = list(self.pids)
                waiting = [
                    pid
                    for pid in pids
                    if observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                        {"pid": pid},
                    )
                ]
                if len(waiting) >= count:
                    return
                Event().wait(0.01)
        pytest.fail("PostgreSQL did not report the expected blocked writers")


def test_two_real_concurrent_api_batches_one_wins_one_is_stale() -> None:
    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    cookie = a.cookies.get("ht_demo_session")
    ready = Barrier(2)

    def write() -> int:
        other_connection = TestClient(app)
        other_connection.cookies.set("ht_demo_session", cookie)
        ready.wait(timeout=5)
        return other_connection.post(
            "/api/v1/kennel-map/moves", json=change
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        with SessionLocal.begin() as holder:
            holder.scalar(
                select(DemoWorkspace)
                .where(DemoWorkspace.id == workspace_id(a))
                .with_for_update()
            )
            attempt = LockAttempt()
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                futures = [pool.submit(write) for _ in range(2)]
                attempt.assert_blocked(2)
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert sorted(future.result(timeout=15) for future in futures) == [200, 409]
    assert snapshot(a)["housing_edit"]["revision"] == 1
    assert_baseline()


def test_reset_wins_real_lock_race_stale_batch_cannot_restore() -> None:
    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    identity = workspace_id(a)
    attempt = LockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as session:
            DemoWorkspaceService(session, identity).reset()
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(a.post, "/api/v1/kennel-map/moves", json=change)
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=10).status_code == 409
    assert homes(snapshot(a))["Atlas"] == "A1-01"
    assert_baseline()


def test_move_wins_real_lock_race_following_reset_removes_it() -> None:
    from app.schemas.kennel_map import HousingMovesRequest
    from app.services.housing_move_service import HousingMoveService

    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    attempt = LockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as session:
            HousingMoveService(
                session, DemoClock.from_settings(get_settings()), workspace_id(a)
            ).apply(HousingMovesRequest.model_validate(change))
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(a.post, "/api/v1/demo/reset")
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=10).status_code == 200
    assert snapshot(a)["housing_edit"]["revision"] == 2
    assert homes(snapshot(a))["Atlas"] == "A1-01"


def test_expiry_cleanup_wins_lock_race_and_writer_fails_closed() -> None:
    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    identity = workspace_id(a)
    attempt = LockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as session:
            workspace = session.scalar(
                select(DemoWorkspace)
                .where(DemoWorkspace.id == identity)
                .with_for_update()
            )
            assert workspace is not None
            workspace.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.flush()
            assert cleanup_expired_workspaces(session) == 1
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(a.post, "/api/v1/kennel-map/moves", json=change)
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        assert future.result(timeout=10).status_code == 401
    assert snapshot(a)["housing_edit"]["editable"] is False
    assert_baseline()


def test_snapshot_waits_for_move_and_returns_matching_revision_and_occupancy() -> None:
    from app.schemas.kennel_map import HousingMovesRequest
    from app.services.housing_move_service import HousingMoveService

    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    identity = workspace_id(a)
    attempt = LockAttempt()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as session:
            expected = HousingMoveService(
                session, DemoClock.from_settings(get_settings()), identity
            ).apply(HousingMovesRequest.model_validate(change))
            event.listen(engine, "before_cursor_execute", attempt)
            try:
                future = pool.submit(a.get, "/api/v1/kennel-map")
                attempt.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", attempt)
        response = future.result(timeout=10)
        assert response.status_code == 200
        assert response.json() == expected.model_dump(mode="json")


def test_cleanup_after_locked_move_cascades_without_partial_orphan_rows() -> None:
    from app.schemas.kennel_map import HousingMovesRequest
    from app.services.housing_move_service import HousingMoveService

    a = client()
    change = payload(a, ("Atlas", "A2-01"))
    identity = workspace_id(a)
    attempted = Event()
    cleanup_pid: list[int] = []

    def observed(*args: Any) -> None:
        if args[2].startswith("DELETE FROM demo_workspaces"):
            cleanup_pid.append(args[0].connection.driver_connection.info.backend_pid)
            attempted.set()

    def cleanup() -> int:
        with SessionLocal.begin() as session:
            # Include the committed old expiry too, so cleanup must wait for the row.
            return cleanup_expired_workspaces(
                session, now=datetime.now(UTC) + timedelta(days=2)
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionLocal.begin() as session:
            HousingMoveService(
                session, DemoClock.from_settings(get_settings()), identity
            ).apply(HousingMovesRequest.model_validate(change))
            workspace = session.get(DemoWorkspace, identity)
            assert workspace is not None
            workspace.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.flush()
            event.listen(engine, "before_cursor_execute", observed)
            try:
                future = pool.submit(cleanup)
                assert attempted.wait(5)
                probe = LockAttempt()
                probe.pids.update(cleanup_pid)
                probe.attempted.set()
                probe.assert_blocked()
                assert not future.done()
            finally:
                event.remove(engine, "before_cursor_execute", observed)
        assert future.result(timeout=10) == 1
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM demo_workspace_housing_overrides"
            ).scalar_one()
            == 0
        )
    assert_baseline()


def test_guarded_global_reset_clears_overrides_and_restores_canonical_world() -> None:
    a = client()
    assert (
        a.post(
            "/api/v1/kennel-map/moves", json=payload(a, ("Atlas", "PUPPY-A"))
        ).status_code
        == 200
    )
    with SessionLocal.begin() as session:
        reset_demo_world(
            session, DemoClock.from_settings(get_settings()), require_enabled=False
        )
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM demo_workspace_housing_overrides"
            ).scalar_one()
            == 0
        )
    assert homes(snapshot(a))["Atlas"] == "A1-01"
    assert snapshot(a)["housing_edit"]["editable"] is False
    assert_baseline()


def test_workspace_freedom_does_not_weaken_canonical_capacity_validator() -> None:
    a = client()
    assert (
        a.post(
            "/api/v1/kennel-map/moves", json=payload(a, ("Atlas", "PUPPY-A"))
        ).status_code
        == 200
    )
    assert_baseline()
    # Change a canonical row only inside a rolled-back isolated test transaction.
    with SessionLocal() as session:
        atlas = session.scalar(select(Dog).where(Dog.name == "Atlas"))
        location = session.scalar(
            select(KennelLocation).where(KennelLocation.code == "PUPPY-A")
        )
        assert atlas is not None and location is not None
        period = session.scalar(
            select(HousingAssignment).where(
                HousingAssignment.dog_id == atlas.id,
                HousingAssignment.valid_to.is_(None),
            )
        )
        assert period is not None
        period.location_id = location.id
        session.flush()
        with pytest.raises(DemoValidationError):
            validate_demo_world(session, DemoClock.from_settings(get_settings()))
        session.rollback()
    assert_baseline()


def test_normal_logs_do_not_echo_cookie_precondition_or_move_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    a = client()
    change = payload(a, ("Atlas", "PUPPY-A"))
    caplog.clear()
    assert a.post("/api/v1/kennel-map/moves", json=change).status_code == 200
    text = caplog.text
    assert a.cookies.get("ht_demo_session") not in text
    assert change["precondition"] not in text
    assert "destination_code" not in text
    assert dog_id("Atlas") not in text


def test_current_override_never_fills_a_real_historical_assignment_gap() -> None:
    a = client()
    with SessionLocal.begin() as session:
        assignment = session.scalar(
            select(HousingAssignment)
            .join(Dog)
            .where(Dog.name == "Atlas", HousingAssignment.valid_to.is_(None))
        )
        assert assignment is not None
        identity, original_start = assignment.id, assignment.valid_from
        assignment.valid_from = date(2026, 3, 30)
    try:
        assert (
            a.post(
                "/api/v1/kennel-map/moves", json=payload(a, ("Atlas", "B2-01"))
            ).status_code
            == 200
        )
        assert homes(snapshot(a))["Atlas"] == "B2-01"
        assert "Atlas" not in homes(snapshot(a, "2026-03-29"))
        response = a.get(
            "/api/v1/daily-plans/2026-03-29/eligible-dogs",
            params={"activity_type": "training", "distance_km": 5},
        )
        assert response.status_code == 200
        atlas = next(dog for dog in response.json()["dogs"] if dog["name"] == "Atlas")
        assert atlas["housing_code"] is None
        entry = a.get("/api/v1/daily-entry/2026-03-29")
        assert entry.status_code == 200
        found = [
            dog
            for group in entry.json()["housing_groups"]
            for dog in group["dogs"]
            if dog["name"] == "Atlas"
        ]
        assert len(found) == 1 and found[0]["housing_code"] is None
    finally:
        with SessionLocal.begin() as session:
            assignment = session.get(HousingAssignment, identity)
            assert assignment is not None
            assignment.valid_from = original_start
    assert_baseline()
