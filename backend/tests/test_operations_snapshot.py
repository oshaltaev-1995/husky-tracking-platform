"""Agent reads on explicitly identified disposable PostgreSQL, never public data."""

import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Event
from time import monotonic
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.service import reset_demo_world
from app.main import app
from app.models import (
    DailyPlan,
    DemoWorkspace,
    DemoWorkspaceDay,
    DemoWorkspaceHousingOverride,
    Dog,
    DogRelationshipConstraint,
    DogRoleCapability,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)
from app.operations.foundation import prepare_review
from app.operations.policy import ProviderRun
from app.operations.provider_models import (
    AgentFailure,
    HttpReply,
    HttpRequest,
    ProviderSettings,
    ToolContract,
)
from app.operations.schemas import OperationError
from app.operations.snapshot import SnapshotReader
from app.operations.tools import FrozenTools
from app.services.daily_plan_service import DailyPlanService
from app.services.demo_workspace_service import resolve_workspace
from app.services.kennel_map_read_service import KennelMapReadService

DAY = date(2026, 3, 29)
REFERENCE = date(2026, 3, 31)


@pytest.fixture(autouse=True)
def disposable_world() -> Iterator[None]:
    if os.environ.get("P13F_DISPOSABLE_DB_CONFIRMED") != "1":
        pytest.skip(
            "Operations tests require the explicitly confirmed disposable PostgreSQL"
        )
    assert engine.url.get_backend_name() == "postgresql"
    assert engine.url.host == "127.0.0.1"
    assert engine.url.database == "husky_tracking"
    with SessionLocal.begin() as session:
        reset_demo_world(session, clock(), require_enabled=False)
    yield
    app.dependency_overrides.clear()


def clock() -> DemoClock:
    return DemoClock.from_settings(get_settings())


def reader() -> SnapshotReader:
    return SnapshotReader(SessionLocal, clock(), get_settings().demo_session_secret)


def visitor() -> TestClient:
    result = TestClient(app)
    assert result.get("/api/v1/demo/session").status_code == 200
    return result


def token(client: TestClient) -> str:
    value = client.cookies.get("ht_demo_session")
    assert value
    return value


def workspace(client: TestClient) -> int:
    with SessionLocal() as session:
        row = resolve_workspace(
            session, token(client), get_settings().demo_session_secret
        )
        assert row is not None
        return row.id


def dog_ids(*names: str) -> list[str]:
    with SessionLocal() as session:
        found = {
            name: public_id
            for name, public_id in session.execute(select(Dog.name, Dog.public_id))
        }
    return [str(found[name]) for name in names]


def create_training(
    client: TestClient,
    names: list[str],
    *,
    day: date = DAY,
    revision: int | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/daily-plans/{day}/activities",
        json={
            "activity_type": "training",
            "title": "Synthetic test loop",
            "distance_km": 5,
            "participant_ids": dog_ids(*names),
            "expected_revision": revision,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def graph_counts() -> dict[str, int]:
    models = (
        DemoWorkspace,
        DemoWorkspaceDay,
        DemoWorkspaceHousingOverride,
        DailyPlan,
        PlannedActivity,
        PlannedActivityParticipant,
        PlannedTeam,
        PlannedTeamSlot,
        WorkSession,
        WorkParticipation,
    )
    with SessionLocal() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            or 0
            for model in models
        }


def expect_error(code: str, operation: Any) -> None:
    with pytest.raises(OperationError) as failure:
        operation()
    assert failure.value.code == code


def test_missing_cookie_invalid_date_and_expiry_never_initialize_a_workspace() -> None:
    service = reader()
    before = graph_counts()
    expect_error("session_required", lambda: service.capture(None, DAY))
    expect_error(
        "session_expired", lambda: service.capture("not-a-valid-workspace-cookie", DAY)
    )
    for when in (date(2025, 11, 30), date(2026, 4, 1)):
        expect_error("date_out_of_range", lambda when=when: service.capture(None, when))
    assert graph_counts() == before
    client = visitor()
    context = service.capture(token(client), DAY)
    own_id = workspace(client)
    with SessionLocal.begin() as session:
        session.get(DemoWorkspace, own_id).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    after_expiry = graph_counts()
    expect_error("session_expired", lambda: service.capture(token(client), DAY))
    expect_error("session_expired", lambda: service.check(context, token(client)))
    assert graph_counts() == after_expiry


def test_capture_is_detached_immutable_and_has_no_flush_dml_or_materialization() -> (
    None
):
    client = visitor()
    note = "Synthetic note excluded from the provider projection"
    response = client.put(
        f"/api/v1/daily-plans/{DAY}",
        json={"notes": note, "expected_revision": None},
    )
    assert response.status_code == 200, response.text
    before = graph_counts()
    statements: list[str] = []
    flushes: list[bool] = []

    def record_sql(_: Any, __: Any, statement: str, *___: Any) -> None:
        if statement.lstrip().split(" ", 1)[0].upper() in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
        }:
            statements.append(statement.split(" ", 1)[0])

    def record_flush(*_: Any) -> None:
        flushes.append(True)

    event.listen(engine, "before_cursor_execute", record_sql)
    event.listen(Session, "before_flush", record_flush)
    try:
        service = reader()
        context = service.capture(token(client), DAY)
        service.check(context, token(client))
        serialized = context.snapshot.model_dump_json()
        assert note not in serialized and token(client) not in serialized
        assert "precondition" not in serialized and "workspace_id" not in serialized
        tools = FrozenTools(context.snapshot)
        tools.execute("get_day_plan", json.dumps({"selected_date": str(DAY)}))
        assert not statements and not flushes
    finally:
        event.remove(engine, "before_cursor_execute", record_sql)
        event.remove(Session, "before_flush", record_flush)
    assert graph_counts() == before
    assert context.snapshot.plan_exists and not context.snapshot.activities
    with pytest.raises(ValidationError):
        context.snapshot.plan_exists = False
    with pytest.raises(ValidationError):
        context.snapshot.dogs[0].name = "Changed after capture"


def test_two_initialized_workspaces_housing_history_and_reset_are_isolated() -> None:
    a, b = visitor(), visitor()
    first = create_training(a, ["Atlas"])
    second = create_training(b, ["Freya"])
    current = a.get("/api/v1/kennel-map").json()
    moved = a.post(
        "/api/v1/kennel-map/moves",
        json={
            "effective_date": str(REFERENCE),
            "precondition": current["housing_edit"]["precondition"],
            "moves": [{"dog_id": dog_ids("Atlas")[0], "destination_code": "PUPPY-A"}],
        },
    )
    assert moved.status_code == 200, moved.text
    service = reader()
    ca, cb = service.capture(token(a), REFERENCE), service.capture(token(b), REFERENCE)
    atlas_a = next(dog for dog in ca.snapshot.dogs if dog.name == "Atlas")
    atlas_b = next(dog for dog in cb.snapshot.dogs if dog.name == "Atlas")
    assert (atlas_a.housing_code, atlas_a.housing_source) == (
        "PUPPY-A",
        "workspace_override",
    )
    assert (atlas_b.housing_code, atlas_b.housing_source) == ("A1-01", "canonical")
    historical = service.capture(token(a), DAY)
    assert (
        next(
            dog for dog in historical.snapshot.dogs if dog.name == "Atlas"
        ).housing_code
        == "A1-01"
    )
    assert historical.snapshot.activities[0].id == UUID(first["activities"][0]["id"])
    other_day = service.capture(token(b), DAY)
    assert other_day.snapshot.activities[0].id == UUID(second["activities"][0]["id"])
    expect_error(
        "entity_not_in_snapshot",
        lambda: FrozenTools(historical.snapshot).execute(
            "get_day_plan",
            json.dumps(
                {
                    "selected_date": str(DAY),
                    "activity_ids": [second["activities"][0]["id"]],
                }
            ),
        ),
    )
    over_capacity = next(
        location for location in ca.snapshot.locations if location.code == "PUPPY-A"
    )
    assert len(over_capacity.residents) == 6 > over_capacity.nominal_capacity
    assert all(
        check.status == "pass"
        for check in ca.snapshot.checks
        if check.rule == "HOUSING_INFORMATION"
    )
    assert a.post("/api/v1/demo/reset").status_code == 200
    expect_error("context_changed", lambda: service.check(ca, token(a)))
    service.check(cb, token(b))
    after_b = service.capture(token(b), DAY)
    assert after_b.snapshot.activities == other_day.snapshot.activities


def test_reset_replacement_cancel_and_plan_edit_have_distinct_context_contracts() -> (
    None
):
    a, replacement = visitor(), visitor()
    service = reader()
    original = service.capture(token(a), DAY)
    plan = create_training(a, ["Atlas"])
    service.check(
        original, token(a)
    )  # A frozen report can predate an ordinary plan edit.
    assert not original.snapshot.plan_exists
    assert service.capture(token(a), DAY).snapshot.activities[0].id == UUID(
        plan["activities"][0]["id"]
    )
    expect_error("context_changed", lambda: service.check(original, token(replacement)))
    expect_error("cancelled", lambda: service.check(original, token(a), cancelled=True))
    assert a.post("/api/v1/demo/reset").status_code == 200
    expect_error("context_changed", lambda: service.check(original, token(a)))


def test_workload_cutoff_excludes_future_and_keeps_plan_actual_separate() -> None:
    client = visitor()
    plan = create_training(client, ["Atlas"])
    create_training(client, ["Atlas"], revision=plan["revision"])
    service = reader()
    before = service.capture(token(client), DAY)
    atlas_before = next(dog for dog in before.snapshot.dogs if dog.name == "Atlas")
    future = client.post(
        "/api/v1/daily-entry/2026-03-30/sessions",
        json={"distance_km": 10, "participants": [{"dog_id": dog_ids("Atlas")[0]}]},
    )
    assert future.status_code == 200, future.text
    after_future = service.capture(token(client), DAY)
    assert (
        next(dog for dog in after_future.snapshot.dogs if dog.name == "Atlas")
        == atlas_before
    )
    today = client.post(
        f"/api/v1/daily-entry/{DAY}/sessions",
        json={"distance_km": 5, "participants": [{"dog_id": dog_ids("Atlas")[0]}]},
    )
    assert today.status_code == 200, today.text
    after = service.capture(token(client), DAY).snapshot
    atlas_after = next(dog for dog in after.dogs if dog.name == "Atlas")
    assert (
        atlas_after.km_7d_before,
        atlas_after.km_14d_before,
        atlas_after.season_km_before,
    ) == (
        atlas_before.km_7d_before,
        atlas_before.km_14d_before,
        atlas_before.season_km_before,
    )
    assert (atlas_after.actual_km_on_date, atlas_after.starts_on_date) == (5, 1)
    checks = {
        check.rule: check
        for check in after.checks
        if any(ref.id == str(atlas_after.id) for ref in check.entities)
    }
    evidence = {item.id: item for item in after.evidence}
    planned = evidence[checks["PLANNED_DAILY_KM"].evidence_ids[0]]
    actual = evidence[checks["ACTUAL_DAILY_KM"].evidence_ids[0]]
    assert next(item.value for item in planned.values if item.name == "total") == 10
    assert next(item.value for item in actual.values if item.name == "total") == 5


def saved_team(client: TestClient) -> UUID:
    plan = create_training(client, ["Atlas", "Daisy", "Freya", "Kenzo"])
    identity = plan["activities"][0]["id"]
    route = f"/api/v1/daily-plans/{DAY}/activities/{identity}/teams"
    generated = client.post(route + "/generate", json={"team_count": 1, "team_size": 4})
    assert generated.status_code == 200, generated.text
    team = generated.json()["teams"][0]
    payload = {
        "expected_revision": plan["revision"],
        "teams": [
            {
                "sequence": 1,
                "team_size": 4,
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
        ],
    }
    saved = client.put(route, json=payload)
    assert saved.status_code == 200, saved.text
    return UUID(identity)


def test_saved_role_and_pair_validation_reuse_existing_domain_semantics() -> None:
    client = visitor()
    activity_id = saved_team(client)
    service = reader()
    original = service.capture(token(client), DAY).snapshot
    activity = next(item for item in original.activities if item.id == activity_id)
    assert activity.lineup_error is None
    slots = activity.teams[0].slots
    # A hard conflict across two harness pairs is valid on the same team.
    pair_ids = [slots[0].dog_id, slots[2].dog_id]
    with SessionLocal.begin() as session:
        internal = sorted(
            session.scalars(select(Dog.id).where(Dog.public_id.in_(pair_ids)))
        )
        existing = session.scalar(
            select(DogRelationshipConstraint).where(
                DogRelationshipConstraint.dog_a_id == internal[0],
                DogRelationshipConstraint.dog_b_id == internal[1],
                DogRelationshipConstraint.relationship_kind == "hard_conflict",
            )
        )
        if existing is None:
            session.add(
                DogRelationshipConstraint(
                    dog_a_id=internal[0],
                    dog_b_id=internal[1],
                    relationship_kind="hard_conflict",
                )
            )
    assert (
        service.capture(token(client), DAY).snapshot.activities[0].lineup_error is None
    )
    with SessionLocal.begin() as session:
        internal = sorted(
            session.scalars(
                select(Dog.id).where(
                    Dog.public_id.in_([slots[0].dog_id, slots[1].dog_id])
                )
            )
        )
        session.add(
            DogRelationshipConstraint(
                dog_a_id=internal[0],
                dog_b_id=internal[1],
                relationship_kind="hard_conflict",
            )
        )
    assert (
        service.capture(token(client), DAY).snapshot.activities[0].lineup_error
        == "hard_pair_conflict"
    )
    with SessionLocal.begin() as session:
        dog_id = session.scalar(select(Dog.id).where(Dog.public_id == slots[0].dog_id))
        session.execute(
            delete(DogRoleCapability).where(
                DogRoleCapability.dog_id == dog_id, DogRoleCapability.role == "lead"
            )
        )
    assert (
        service.capture(token(client), DAY).snapshot.activities[0].lineup_error
        == "role_mismatch"
    )


def test_effective_birth_availability_and_lifecycle_follow_the_selected_date() -> None:
    client = visitor()
    service = reader()
    january = service.capture(token(client), date(2026, 1, 1)).snapshot
    recovered = service.capture(token(client), date(2026, 1, 10)).snapshot
    before_retirement = service.capture(token(client), date(2026, 2, 14)).snapshot
    retirement = service.capture(token(client), date(2026, 2, 15)).snapshot
    assert (
        next(dog for dog in january.dogs if dog.name == "Maple").availability
        == "injured"
    )
    assert (
        next(dog for dog in recovered.dogs if dog.name == "Maple").availability
        == "available"
    )
    assert not next(dog for dog in january.dogs if dog.name == "Taro").born
    assert (
        next(dog for dog in before_retirement.dogs if dog.name == "Fjord").availability
        == "available"
    )
    fjord = next(dog for dog in retirement.dogs if dog.name == "Fjord")
    assert fjord.lifecycle == "active" and fjord.availability == "retired"


def test_snapshot_lock_precedes_reads_and_blocks_writer_until_detached_capture_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = visitor()
    service = reader()
    own_id = workspace(client)
    captured = Event()
    release = Event()
    writer_started = Event()
    writer_pid: list[int] = []
    original = KennelMapReadService.snapshot

    def paused(self: KennelMapReadService, on_date: date):
        result = original(self, on_date)
        assert (
            self._housing_context is not None
            and self._housing_context.workspace_id == own_id
        )
        captured.set()
        assert release.wait(5)
        return result

    def writer() -> None:
        with SessionLocal.begin() as session:
            writer_pid.append(session.scalar(select(func.pg_backend_pid())))
            writer_started.set()
            DailyPlanService(session, clock(), own_id).update_notes(
                DAY, "Concurrent synthetic note", None
            )

    monkeypatch.setattr(KennelMapReadService, "snapshot", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(service.capture, token(client), DAY)
        assert captured.wait(5)
        writing = pool.submit(writer)
        try:
            assert writer_started.wait(5)
            blocked = False
            deadline = monotonic() + 3
            while monotonic() < deadline:
                with engine.connect() as connection:
                    blocked = connection.execute(
                        text(
                            "SELECT wait_event_type = 'Lock' "
                            "FROM pg_stat_activity WHERE pid=:pid"
                        ),
                        {"pid": writer_pid[0]},
                    ).scalar_one()
                if blocked:
                    break
                Event().wait(0.02)
            assert blocked and not writing.done()
        finally:
            release.set()
        result = reading.result(timeout=5)
        writing.result(timeout=5)
    assert result.snapshot.plan_exists is False
    monkeypatch.setattr(KennelMapReadService, "snapshot", original)
    assert service.capture(token(client), DAY).snapshot.plan_exists is True


def test_provider_transport_has_no_open_capture_transaction_or_lock() -> None:
    client = visitor()
    service = reader()
    context = service.capture(token(client), DAY)
    own_id = workspace(client)
    tools = FrozenTools(context.snapshot)
    observed: list[bool] = []

    def transport(_: HttpRequest) -> HttpReply:
        with SessionLocal.begin() as session:
            assert (
                session.scalar(
                    select(DemoWorkspace.id)
                    .where(DemoWorkspace.id == own_id)
                    .with_for_update(nowait=True)
                )
                == own_id
            )
        observed.append(True)
        answer = {
            "explanation": "No plan is saved.",
            "references": [
                {
                    "snapshot_id": str(context.snapshot.id),
                    "selected_date": str(DAY),
                    "evidence_id": context.snapshot.evidence[0].id,
                    "entity": {"kind": "day", "id": str(DAY)},
                }
            ],
        }
        return HttpReply(
            status=200,
            body=json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": json.dumps(answer)},
                        }
                    ]
                }
            ).encode(),
        )

    contract = next(
        schema for name, schema in tools.contracts() if name == "validate_day"
    )
    run = ProviderRun(
        settings=ProviderSettings(
            enabled=True,
            groq_free_account_confirmed=True,
            groq_api_key=SecretStr("dummy-offline-key"),
        ),
        transport=transport,
        snapshot_id=str(context.snapshot.id),
        snapshot_json=tools.provider_context(),
        task="Review this synthetic date",
        tools=(
            ToolContract(
                name="validate_day",
                description="Read frozen evidence",
                parameters_json=contract,
            ),
        ),
        check_context=lambda: service.check(context, token(client)),
        admit=lambda: True,
    )
    result = run.call()

    def validate(answer: str) -> None:
        tools.validate_references(answer)

    run.finalize(result, validate)
    assert observed == [True]


def tool_reply() -> HttpReply:
    return HttpReply(
        status=200,
        body=json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "offline-read-1",
                                    "type": "function",
                                    "function": {
                                        "name": "validate_day",
                                        "arguments": json.dumps(
                                            {"selected_date": str(DAY)}
                                        ),
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        ).encode(),
    )


def settings(*, reserve_enabled: bool = False) -> ProviderSettings:
    return ProviderSettings(
        enabled=True,
        openrouter_reserve_enabled=reserve_enabled,
        groq_free_account_confirmed=True,
        groq_api_key=SecretStr("offline-primary-fixture"),
        openrouter_api_key=SecretStr("offline-reserve-fixture"),
    )


def test_midrun_fallback_keeps_frozen_snapshot_and_releases_locks_for_every_http() -> (
    None
):
    client = visitor()
    own_id = workspace(client)
    calls: list[HttpRequest] = []
    admissions: list[bool] = []

    def transport(request: HttpRequest) -> HttpReply:
        with SessionLocal.begin() as session:
            assert (
                session.scalar(
                    select(DemoWorkspace.id)
                    .where(DemoWorkspace.id == own_id)
                    .with_for_update(nowait=True)
                )
                == own_id
            )
        calls.append(request)
        if len(calls) == 1:
            return tool_reply()
        if len(calls) == 2:
            return HttpReply(status=429, retry_after="3")
        answer = {
            "explanation": "No saved plan existed at the captured time.",
            "references": [
                {
                    "snapshot_id": str(prepared.context.snapshot.id),
                    "selected_date": str(DAY),
                    "evidence_id": prepared.context.snapshot.evidence[0].id,
                    "entity": {"kind": "day", "id": str(DAY)},
                }
            ],
        }
        return HttpReply(
            status=200,
            body=json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": json.dumps(answer)},
                        }
                    ]
                }
            ).encode(),
        )

    def admit() -> bool:
        admissions.append(True)
        return True

    prepared = prepare_review(
        reader=reader(),
        selected_date=DAY,
        current_cookie=lambda: token(client),
        cancelled=lambda: False,
        settings=settings(reserve_enabled=True),
        transport=transport,
        admit=admit,
    )
    first = prepared.run.call()
    before = graph_counts()
    result = prepared.execute_tool(first)
    assert len(result.model_dump_json().encode()) <= settings().max_tool_result_bytes
    assert graph_counts() == before
    # Ordinary post-capture edits do not mutate/rebuild the captured input on reserve.
    create_training(client, ["Atlas"])
    after_expected_write = graph_counts()
    final = prepared.run.call()
    prepared.finish(final)
    assert graph_counts() == after_expected_write
    assert prepared.context.snapshot.plan_exists is False
    assert reader().capture(token(client), DAY).snapshot.plan_exists is True
    assert (
        prepared.run.http_calls,
        prepared.run.tool_calls,
        prepared.run.switches,
    ) == (
        3,
        1,
        1,
    )
    assert admissions == [True]
    primary, followup, reserve = [json.loads(request.body_json) for request in calls]
    assert primary["messages"] == reserve["messages"]
    assert len(followup["messages"]) > len(reserve["messages"])
    assert calls[0].url == calls[1].url != calls[2].url


@pytest.mark.parametrize(
    ("invalidation", "code"),
    [
        ("reset", "context_changed"),
        ("expiry", "session_expired"),
        ("cancel", "cancelled"),
    ],
)
def test_midrun_invalidations_prevent_any_further_provider_call(
    invalidation: str, code: str
) -> None:
    client = visitor()
    cancelled = [False]
    calls: list[bool] = []

    def transport(_: HttpRequest) -> HttpReply:
        calls.append(True)
        return tool_reply()

    prepared = prepare_review(
        reader=reader(),
        selected_date=DAY,
        current_cookie=lambda: token(client),
        cancelled=lambda: cancelled[0],
        settings=settings(),
        transport=transport,
        admit=lambda: True,
    )
    prepared.execute_tool(prepared.run.call())
    if invalidation == "reset":
        assert client.post("/api/v1/demo/reset").status_code == 200
    elif invalidation == "expiry":
        own_id = workspace(client)
        with SessionLocal.begin() as session:
            session.get(DemoWorkspace, own_id).expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
    else:
        cancelled[0] = True
    with pytest.raises(AgentFailure) as failure:
        prepared.run.call()
    assert failure.value.code == code
    assert calls == [True] and prepared.run.switches == 0


def test_training_day_team_and_actual_projections_fit_normal_agent_budgets() -> None:
    client = visitor()
    review = client.get("/api/v1/training-day-example")
    assert review.status_code == 200
    proposal = review.json()
    assert proposal["available"] is True
    applied = client.post(
        "/api/v1/training-day-example/apply",
        json={
            "date": proposal["date"],
            "preset_version": proposal["preset_version"],
            "participant_ids": [item["id"] for item in proposal["participants"]],
            "precondition": proposal["precondition"],
        },
    )
    assert applied.status_code == 200, applied.text
    service = reader()
    planned = service.capture(token(client), DAY).snapshot
    assert len(planned.activities) == 4 and not planned.actual
    assert all(
        len(activity.participants) == 16 and not activity.teams
        for activity in planned.activities
    )
    assert all(
        activity.actual_status == "not_recorded" for activity in planned.activities
    )
    measurements: dict[str, int] = {}

    def measure(label: str, snapshot: Any) -> None:
        tools = FrozenTools(snapshot)
        checked = tools.execute("validate_day", json.dumps({"selected_date": str(DAY)}))
        measurements[label + "_snapshot_bytes"] = len(
            snapshot.model_dump_json().encode()
        )
        measurements[label + "_validate_day_bytes"] = len(
            checked.model_dump_json().encode()
        )
        assert measurements[label + "_snapshot_bytes"] <= 192_000
        assert (
            measurements[label + "_validate_day_bytes"]
            <= settings().max_tool_result_bytes
        )

    measure("planned", planned)
    first = planned.activities[0]
    route = f"/api/v1/daily-plans/{DAY}/activities/{first.id}/teams"
    generated = client.post(route + "/generate", json={"team_count": 2, "team_size": 8})
    assert generated.status_code == 200, generated.text
    writes = [
        {
            "sequence": team["sequence"],
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
        for team in generated.json()["teams"]
    ]
    saved = client.put(
        route, json={"expected_revision": planned.plan_revision, "teams": writes}
    )
    assert saved.status_code == 200, saved.text
    arranged = service.capture(token(client), DAY).snapshot
    assert [len(activity.teams) for activity in arranged.activities] == [2, 0, 0, 0]
    assert all(activity.lineup_error is None for activity in arranged.activities)
    measure("saved_teams", arranged)
    recorded = client.post(
        f"/api/v1/daily-entry/{DAY}/planned-activities/{first.id}/confirm"
    )
    assert recorded.status_code == 200, recorded.text
    actual = service.capture(token(client), DAY).snapshot
    assert len(actual.actual) == 1 and len(actual.actual[0].participants) == 16
    assert actual.actual[0].distance_km == 5
    assert (
        sum(item.distance_km * len(item.participants) for item in actual.actual) == 80
    )
    assert all(
        activity.actual_status == "not_recorded" for activity in actual.activities[1:]
    )
    assert all(
        dog.actual_km_on_date == 5
        for dog in actual.dogs
        if dog.id in first.participants
    )
    measure("actual", actual)
    print("P14A_BOUNDS", json.dumps(measurements, sort_keys=True))


def test_oversized_activity_graph_is_a_typed_failure_before_graph_projection() -> None:
    client = visitor()
    own_id = workspace(client)
    with SessionLocal.begin() as session:
        plan = DailyPlan(demo_workspace_id=own_id, plan_date=DAY, revision=1)
        plan.activities = [
            PlannedActivity(
                activity_type="rest",
                sequence=index + 1,
                title="Bounded synthetic fixture",
            )
            for index in range(33)
        ]
        session.add(plan)
    before = graph_counts()
    expect_error("snapshot_too_large", lambda: reader().capture(token(client), DAY))
    assert graph_counts() == before
