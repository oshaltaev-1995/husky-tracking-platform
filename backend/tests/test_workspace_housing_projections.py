from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.catalog import EXPECTED_SEMANTIC_CHECKSUM
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.demo.validation import validate_demo_world
from app.main import app
from app.models import (
    DailyPlan,
    DemoWorkspaceDay,
    Dog,
    HousingAssignment,
    PlannedActivity,
    PlannedActivityParticipant,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)

REFERENCE_DATE = "2026-03-31"
HISTORICAL_DATE = "2026-03-29"
FULL_RANGE = {"from": "2025-12-01", "to": REFERENCE_DATE}


@pytest.fixture(autouse=True)
def canonical_demo_world() -> Iterator[None]:
    """Reset-capable integration fixture: run only on the disposable test DB."""
    with SessionLocal.begin() as session:
        reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
    yield


@pytest.fixture
def browsers() -> tuple[TestClient, TestClient]:
    first, second = TestClient(app), TestClient(app)
    for client in (first, second):
        response = client.get("/api/v1/demo/session")
        assert response.status_code == 200, response.text
    return first, second


def get(client: TestClient, path: str, **params: str) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def dog_ids() -> dict[str, str]:
    with SessionLocal() as session:
        return {
            name: str(public_id)
            for name, public_id in session.execute(select(Dog.name, Dog.public_id))
        }


def locations(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["code"]: item for item in snapshot["locations"]}


def resident_codes(snapshot: dict[str, Any]) -> dict[str, str]:
    return {
        dog["name"]: item["code"]
        for item in snapshot["locations"]
        for dog in item["residents"]
    }


def move(
    client: TestClient, destinations: dict[str, str] | None = None
) -> dict[str, Any]:
    ids = dog_ids()
    current = get(client, "/api/v1/kennel-map", date=REFERENCE_DATE)
    response = client.post(
        "/api/v1/kennel-map/moves",
        json={
            "effective_date": REFERENCE_DATE,
            "precondition": current["housing_edit"]["precondition"],
            "moves": [
                {"dog_id": ids[name], "destination_code": code}
                for name, code in (
                    destinations or {"Aurora": "PUPPY-A", "Atlas": "B1-05"}
                ).items()
            ],
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def stored_rows() -> dict[str, list[tuple[object, ...]]]:
    """Include ledger geometry, plan revisions, and canonical housing, not overrides."""
    models = (
        HousingAssignment,
        DailyPlan,
        PlannedActivity,
        PlannedActivityParticipant,
        PlannedTeam,
        PlannedTeamSlot,
        WorkSession,
        WorkParticipation,
        DemoWorkspaceDay,
    )
    with SessionLocal() as session:
        return {
            model.__tablename__: [
                tuple(row)
                for row in session.execute(
                    select(model.__table__).order_by(model.__table__.c.id)
                )
            ]
            for model in models
        }


def assert_canonical_baseline() -> None:
    with SessionLocal() as session:
        assert semantic_checksum(session) == EXPECTED_SEMANTIC_CHECKSUM
        validate_demo_world(session, DemoClock.from_settings(get_settings()))


def create_training(client: TestClient, names: list[str]) -> dict[str, Any]:
    ids = dog_ids()
    response = client.post(
        f"/api/v1/daily-plans/{REFERENCE_DATE}/activities",
        json={
            "activity_type": "training",
            "start_time": "09:00:00",
            "title": "5 km Training Loop",
            "distance_km": 5,
            "participant_ids": [ids[name] for name in names],
            "expected_revision": None,
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def save_team(client: TestClient, plan: dict[str, Any]) -> str:
    activity_id: str = plan["activities"][0]["id"]
    base = f"/api/v1/daily-plans/{REFERENCE_DATE}/activities/{activity_id}"
    generated = client.post(
        f"{base}/teams/generate", json={"team_count": 1, "team_size": 4}
    )
    assert generated.status_code == 200, generated.text
    teams = [
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
        for team in generated.json()["teams"]
    ]
    saved = client.put(
        f"{base}/teams",
        json={"expected_revision": plan["revision"], "teams": teams},
    )
    assert saved.status_code == 200, saved.text
    return base


def test_map_registry_profile_and_history_share_only_the_own_housing_overlay(
    browsers: tuple[TestClient, TestClient],
) -> None:
    first, second = browsers
    ids = dog_ids()
    before = get(first, "/api/v1/kennel-map", date=REFERENCE_DATE)
    historical = get(first, "/api/v1/kennel-map", date=HISTORICAL_DATE)
    profile = get(first, f"/api/v1/dogs/{ids['Aurora']}")
    history = get(first, f"/api/v1/dogs/{ids['Aurora']}/history")
    persisted = stored_rows()
    changed = move(first)
    changed_locations = locations(changed)
    original_locations = locations(before)
    assert changed["summary"]["resident_dogs"] == before["summary"]["resident_dogs"]
    assert changed["summary"]["occupied_locations"] == 21
    assert not changed_locations["A1-01"]["residents"]
    for code, added in (("PUPPY-A", "Aurora"), ("B1-05", "Atlas")):
        before_names = {dog["name"] for dog in original_locations[code]["residents"]}
        after_names = {dog["name"] for dog in changed_locations[code]["residents"]}
        assert after_names == before_names | {added}
        assert len(after_names) > changed_locations[code]["capacity"]
    assert resident_codes(get(second, "/api/v1/kennel-map")) == resident_codes(before)
    assert (
        get(first, "/api/v1/kennel-map", date=HISTORICAL_DATE)["locations"]
        == (historical["locations"])
    )

    for params in ({"search": "PUPPY-A"}, {"housing": "PUPPY-A"}):
        found = get(first, "/api/v1/dogs", **params)
        assert {item["name"] for item in found["items"]} == {
            dog["name"] for dog in changed_locations["PUPPY-A"]["residents"]
        }
        assert "Aurora" not in {
            item["name"] for item in get(second, "/api/v1/dogs", **params)["items"]
        }
    by_old_home = get(first, "/api/v1/dogs", search="A1-01")
    assert by_old_home["items"] == []
    registry = get(first, "/api/v1/dogs", sort="housing")
    keys = [
        (item["state"]["housing"]["code"], item["name"]) for item in registry["items"]
    ]
    assert keys == sorted(keys)
    assert registry["housing_groups"] == ["A1", "A2", "B1", "B2", "PUPPY"]
    assert all(
        item["state"]["housing"]["code"] == resident_codes(changed)[item["name"]]
        for item in registry["items"]
    )

    current = get(first, f"/api/v1/dogs/{ids['Aurora']}")
    assert current["state"]["housing"]["code"] == "PUPPY-A"
    assert current["last_known_housing"] == profile["last_known_housing"]
    assert current["last_known_housing"]["code"] == "A1-01"
    assert get(second, f"/api/v1/dogs/{ids['Aurora']}") == profile
    new_history = get(first, f"/api/v1/dogs/{ids['Aurora']}/history")
    assert new_history["housing"] == history["housing"]
    assert new_history["workspace_housing"] == {
        "effective_date": REFERENCE_DATE,
        "location": current["state"]["housing"],
    }
    assert get(second, f"/api/v1/dogs/{ids['Aurora']}/history") == history
    assert stored_rows() == persisted
    assert_canonical_baseline()


def test_population_and_dashboard_use_housing_without_changing_workload(
    browsers: tuple[TestClient, TestClient],
) -> None:
    first, second = browsers
    ids = dog_ids()
    summary = get(first, "/api/v1/analytics/overview", **FULL_RANGE)
    population = get(first, "/api/v1/analytics/population", date=REFERENCE_DATE)
    historical = get(first, "/api/v1/analytics/population", date=HISTORICAL_DATE)
    dashboard = get(first, "/api/v1/dashboard", date=REFERENCE_DATE)
    work = get(first, f"/api/v1/dogs/{ids['Aurora']}/work")
    dog_before = get(first, "/api/v1/analytics/dogs", **FULL_RANGE, search="Aurora")
    persisted = stored_rows()
    changed = move(first)

    current = get(first, "/api/v1/analytics/population", date=REFERENCE_DATE)
    previous_buckets = {
        item["key"]: item["count"] for item in population["housing_areas"]
    }
    current_buckets = {item["key"]: item["count"] for item in current["housing_areas"]}
    assert current_buckets == {
        **previous_buckets,
        "zone_a": previous_buckets["zone_a"] - 2,
        "zone_b": previous_buckets["zone_b"] + 1,
        "PUPPY-A": previous_buckets["PUPPY-A"] + 1,
    }
    assert {key: value for key, value in current.items() if key != "housing_areas"} == {
        key: value for key, value in population.items() if key != "housing_areas"
    }
    assert (
        get(second, "/api/v1/analytics/population", date=REFERENCE_DATE) == population
    )
    assert (
        get(first, "/api/v1/analytics/population", date=HISTORICAL_DATE) == historical
    )

    after_dog = get(first, "/api/v1/analytics/dogs", **FULL_RANGE, search="Aurora")
    expected_dog = {
        **dog_before["items"][0],
        "housing_code": "PUPPY-A",
        "housing_zone": "PUPPY",
    }
    assert after_dog["items"] == [expected_dog]
    older = get(
        first,
        "/api/v1/analytics/dogs",
        **{"from": "2025-12-01", "to": HISTORICAL_DATE, "search": "Aurora"},
    )
    assert older["items"][0]["housing_code"] == "A1-01"
    assert get(first, "/api/v1/analytics/overview", **FULL_RANGE) == summary
    assert get(first, f"/api/v1/dogs/{ids['Aurora']}/work") == work
    after_dashboard = get(first, "/api/v1/dashboard", date=REFERENCE_DATE)
    assert (
        after_dashboard["population"]["occupied_locations"]
        == changed["summary"]["occupied_locations"]
    )
    assert (
        after_dashboard["population"]["resident_dogs"]
        == changed["summary"]["resident_dogs"]
    )
    assert after_dashboard["population"]["housing_areas"] == {
        item["label"]: item["count"] for item in current["housing_areas"]
    }
    for key in ("plan", "actual", "attention", "recent_weekly"):
        assert after_dashboard[key] == dashboard[key]
    assert get(second, "/api/v1/dashboard", date=REFERENCE_DATE) == dashboard
    move(first, {"Hazel": "PUPPY-A"})
    unavailable = get(first, "/api/v1/dashboard", date=REFERENCE_DATE)[
        "unavailable_dogs"
    ]
    hazel = next(item for item in unavailable if item["name"] == "Hazel")
    assert hazel["availability"] == "injured"
    assert hazel["housing_code"] == "PUPPY-A"
    assert get(second, "/api/v1/dashboard", date=REFERENCE_DATE) == dashboard
    assert stored_rows() == persisted
    assert_canonical_baseline()


def test_plan_and_team_candidates_share_housing_but_saved_lineups_do_not_change(
    browsers: tuple[TestClient, TestClient],
) -> None:
    first, _ = browsers
    plan = create_training(first, ["Atlas", "Olive", "Daisy", "Freya"])
    base = save_team(first, plan)
    saved = get(first, f"{base}/team-builder")
    previous_plan = get(first, f"/api/v1/daily-plans/{REFERENCE_DATE}")
    eligible = get(
        first,
        f"/api/v1/daily-plans/{REFERENCE_DATE}/eligible-dogs",
        activity_type="training",
        distance_km="5",
    )
    persisted = stored_rows()
    move(first)
    current_plan = get(first, f"/api/v1/daily-plans/{REFERENCE_DATE}")
    assert current_plan["revision"] == previous_plan["revision"]
    before_activity = previous_plan["activities"][0]
    after_activity = current_plan["activities"][0]
    assert after_activity == {
        **before_activity,
        "participants": [
            {**item, "housing_code": "B1-05"} if item["name"] == "Atlas" else item
            for item in before_activity["participants"]
        ],
    }
    new_eligible = get(
        first,
        f"/api/v1/daily-plans/{REFERENCE_DATE}/eligible-dogs",
        activity_type="training",
        distance_km="5",
    )
    destinations = {"Aurora": "PUPPY-A", "Atlas": "B1-05"}
    assert new_eligible["dogs"] == [
        {**item, "housing_code": destinations[item["name"]]}
        if item["name"] in destinations
        else item
        for item in eligible["dogs"]
    ]
    after = get(first, f"{base}/team-builder")
    assert after["activity"] == saved["activity"]
    assert after["relationships"] == saved["relationships"]
    assert after["candidates"] == [
        {**item, "housing_code": "B1-05"} if item["name"] == "Atlas" else item
        for item in saved["candidates"]
    ]
    # Reopening retains stored teams; future generation may prefer new homes.
    for old_team, new_team in zip(
        saved["saved_teams"], after["saved_teams"], strict=True
    ):
        assert {key: value for key, value in old_team.items() if key != "slots"} == {
            key: value for key, value in new_team.items() if key != "slots"
        }
        assert [
            {key: value for key, value in slot.items() if key != "explanations"}
            for slot in old_team["slots"]
        ] == [
            {key: value for key, value in slot.items() if key != "explanations"}
            for slot in new_team["slots"]
        ]
    generated = first.post(
        f"{base}/teams/generate", json={"team_count": 1, "team_size": 4}
    )
    assert generated.status_code == 200, generated.text
    home_slots = [
        slot
        for team in generated.json()["teams"]
        for slot in team["slots"]
        if slot["dog_name"] in {"Atlas", "Olive"}
    ]
    assert len(home_slots) == 2
    assert len({slot["pair_index"] for slot in home_slots}) == 1
    assert all("Home pair" in slot["explanations"] for slot in home_slots)
    assert stored_rows() == persisted
    assert_canonical_baseline()


def test_actual_groups_participants_and_find_data_change_labels_only(
    browsers: tuple[TestClient, TestClient],
) -> None:
    first, second = browsers
    ids = dog_ids()
    created = first.post(
        f"/api/v1/daily-entry/{REFERENCE_DATE}/sessions",
        json={
            "distance_km": 5,
            "label": "Existing isolated work",
            "participants": [{"dog_id": ids[name]} for name in ("Aurora", "Atlas")],
        },
    )
    assert created.status_code == 200, created.text
    previous = created.json()
    other = get(second, f"/api/v1/daily-entry/{REFERENCE_DATE}")
    old_day = get(first, f"/api/v1/daily-entry/{HISTORICAL_DATE}")
    persisted = stored_rows()
    move(first)
    current = get(first, f"/api/v1/daily-entry/{REFERENCE_DATE}")
    assert current["summary"] == previous["summary"]
    destinations = {"Aurora": "PUPPY-A", "Atlas": "B1-05"}
    expected_sessions = [
        {
            **row,
            "participants": [
                {**item, "housing_code": destinations[item["dog_name"]]}
                if item["dog_name"] in destinations
                else item
                for item in row["participants"]
            ],
        }
        for row in previous["sessions"]
    ]
    assert current["sessions"] == expected_sessions
    located = {
        dog["name"]: (group["code"], dog["housing_code"])
        for group in current["housing_groups"]
        for dog in group["dogs"]
    }
    assert located["Aurora"] == ("PUPPY-A", "PUPPY-A")
    assert located["Atlas"] == ("B1-05", "B1-05")
    assert (
        len(located)
        == sum(len(group["dogs"]) for group in current["housing_groups"])
        == 50
    )
    assert get(second, f"/api/v1/daily-entry/{REFERENCE_DATE}") == other
    assert get(first, f"/api/v1/daily-entry/{HISTORICAL_DATE}") == old_day
    assert stored_rows() == persisted
    assert_canonical_baseline()


def test_historical_gaps_and_archived_last_known_stay_canonical(
    browsers: tuple[TestClient, TestClient],
) -> None:
    first, _ = browsers
    ids = dog_ids()
    profile = get(first, f"/api/v1/dogs/{ids['Django']}")
    history = get(first, f"/api/v1/dogs/{ids['Django']}/history")
    assert profile["state"]["housing"] is None
    assert profile["last_known_housing"] is not None
    move(first)
    assert get(first, f"/api/v1/dogs/{ids['Django']}") == profile
    assert get(first, f"/api/v1/dogs/{ids['Django']}/history") == history
    assert history["workspace_housing"] is None
    for day in ("2025-12-14", "2025-12-15"):
        assert "Django" not in resident_codes(
            get(first, "/api/v1/kennel-map", date=day)
        )
    eligibility = get(
        first,
        "/api/v1/daily-plans/2025-12-14/eligible-dogs",
        activity_type="training",
        distance_km="5",
    )
    django = next(row for row in eligibility["dogs"] if row["name"] == "Django")
    assert django["housing_code"] is None
    assert_canonical_baseline()


def test_each_projection_loads_only_one_scoped_housing_overlay(
    browsers: tuple[TestClient, TestClient],
) -> None:
    first, _ = browsers
    ids = dog_ids()
    plan = create_training(first, ["Atlas", "North", "Daisy", "Freya"])
    activity_id = plan["activities"][0]["id"]
    move(first)
    statements: list[str] = []

    def record(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if "FROM demo_workspace_housing_overrides" in statement:
            statements.append(statement)

    routes = [
        ("/api/v1/kennel-map", {}),
        ("/api/v1/dogs", {}),
        (f"/api/v1/dogs/{ids['Aurora']}", {}),
        (f"/api/v1/dogs/{ids['Aurora']}/history", {}),
        (f"/api/v1/daily-plans/{REFERENCE_DATE}", {}),
        (
            f"/api/v1/daily-plans/{REFERENCE_DATE}/eligible-dogs",
            {"activity_type": "training", "distance_km": "5"},
        ),
        (
            f"/api/v1/daily-plans/{REFERENCE_DATE}/activities/{activity_id}/team-builder",
            {},
        ),
        (f"/api/v1/daily-entry/{REFERENCE_DATE}", {}),
        ("/api/v1/analytics/population", {"date": REFERENCE_DATE}),
        ("/api/v1/analytics/dogs", FULL_RANGE),
        ("/api/v1/dashboard", {"date": REFERENCE_DATE}),
    ]
    event.listen(engine, "before_cursor_execute", record)
    try:
        for path, params in routes:
            statements.clear()
            get(first, path, **params)
            assert len(statements) == 1, path
            assert "demo_workspace_housing_overrides.workspace_id =" in statements[0]
    finally:
        event.remove(engine, "before_cursor_execute", record)
