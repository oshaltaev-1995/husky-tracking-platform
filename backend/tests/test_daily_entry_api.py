from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.main import app
from app.models import DailyPlan, Dog, PlannedTeam, WorkSession

BASELINE_CHECKSUM = "2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2"
MULTI_ROLE = ["Atlas", "Daisy", "Freya", "Kenzo"]


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


def participant(name: str, **geometry: object) -> dict[str, object]:
    return {"dog_id": dog_ids(name)[0], **geometry}


def actual_payload(
    names: list[str],
    *,
    distance: int = 10,
    label: str = "Manual training",
) -> dict[str, object]:
    return {
        "distance_km": distance,
        "start_time": "09:15:00",
        "label": label,
        "note": "Synthetic actual note.",
        "participants": [participant(name) for name in names],
    }


def create_training(
    client: TestClient,
    names: list[str],
    *,
    plan_date: str = "2026-03-29",
    distance: int = 10,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/daily-plans/{plan_date}/activities",
        json={
            "activity_type": "training",
            "start_time": "08:30:00",
            "title": "Forest Loop",
            "distance_km": distance,
            "notes": "Plan note remains separate.",
            "participant_ids": dog_ids(*names),
            "expected_revision": None,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def save_generated_team(
    client: TestClient,
    plan: dict[str, object],
    *,
    plan_date: str = "2026-03-29",
) -> dict[str, object]:
    activity = plan["activities"][0]  # type: ignore[index]
    base = f"/api/v1/daily-plans/{plan_date}/activities/{activity['id']}"  # type: ignore[index]
    generated_response = client.post(
        f"{base}/teams/generate", json={"team_count": 1, "team_size": 4}
    )
    assert generated_response.status_code == 200, generated_response.text
    generated = generated_response.json()
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
        for team in generated["teams"]
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
    return saved.json()


def test_seeded_actual_reopens_with_exact_totals_and_no_side_effect(
    client: TestClient,
) -> None:
    first = client.get("/api/v1/daily-entry/2026-03-31")
    second = client.get("/api/v1/daily-entry/2026-03-31")
    assert first.status_code == 200
    assert first.json() == second.json()
    entry = first.json()
    assert entry["summary"] == {
        "actual_sessions": 2,
        "dogs_worked": 16,
        "dog_starts": 16,
        "total_dog_km": 120,
    }
    assert {item["source"] for item in entry["sessions"]} == {"seeded"}
    assert {item["distance_km"] for item in entry["sessions"]} == {5, 10}


def test_manual_actual_round_trip_edit_delete_and_profile_ledger(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json=actual_payload(["Atlas", "Aurora"]),
    )
    assert created.status_code == 200, created.text
    saved = created.json()["sessions"][0]
    assert saved["source"] == "manual"
    assert [item["dog_name"] for item in saved["participants"]] == [
        "Atlas",
        "Aurora",
    ]

    update = actual_payload(["Atlas"], distance=5, label="Short actual")
    update["expected_revision"] = saved["revision"]
    changed = client.patch(
        f"/api/v1/daily-entry/2026-03-29/sessions/{saved['id']}", json=update
    )
    assert changed.status_code == 200, changed.text
    current = changed.json()["sessions"][0]
    assert current["revision"] == 2
    assert current["distance_km"] == 5
    assert current["participants"][0]["dog_name"] == "Atlas"

    profile = client.get(f"/api/v1/dogs/{dog_ids('Atlas')[0]}/work").json()
    assert any(
        item["date"] == "2026-03-29" and item["distance_km"] == 5
        for item in profile["entries"]
    )

    removed = client.delete(
        f"/api/v1/daily-entry/2026-03-29/sessions/{saved['id']}",
        params={"expected_revision": 2},
    )
    assert removed.status_code == 200
    assert removed.json()["sessions"] == []


def test_plan_confirmation_copies_saved_lineup_and_is_idempotent(
    client: TestClient,
) -> None:
    plan = create_training(client, MULTI_ROLE)
    save_generated_team(client, plan)
    activity_id = plan["activities"][0]["id"]  # type: ignore[index]
    url = f"/api/v1/daily-entry/2026-03-29/planned-activities/{activity_id}/confirm"
    first = client.post(url)
    second = client.post(url)
    assert first.status_code == second.status_code == 200
    actual = first.json()["sessions"][0]
    assert actual == second.json()["sessions"][0]
    assert actual["source"] == "planned"
    assert actual["plan_status"] == "matches_plan"
    assert actual["team_count"] == 1
    assert {item["side"] for item in actual["participants"]} == {"left", "right"}
    assert {item["assigned_role"] for item in actual["participants"]} == {
        "lead",
        "wheel",
    }
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(WorkSession)) == 141


def test_confirmation_without_team_uses_pool_and_non_training_is_rejected(
    client: TestClient,
) -> None:
    plan = create_training(client, ["Atlas", "Aurora"])
    activity = plan["activities"][0]  # type: ignore[index]
    response = client.post(
        f"/api/v1/daily-entry/2026-03-29/planned-activities/{activity['id']}/confirm"  # type: ignore[index]
    )
    assert response.status_code == 200, response.text
    actual = response.json()["sessions"][0]
    assert actual["team_count"] == 0
    assert actual["deviations"] == ["No saved planned lineup"]
    assert all(item["side"] is None for item in actual["participants"])

    walk = client.post(
        "/api/v1/daily-plans/2026-03-30/activities",
        json={
            "activity_type": "open_space_walk",
            "start_time": None,
            "title": "Yard walk",
            "distance_km": None,
            "notes": None,
            "participant_ids": dog_ids("Atlas"),
            "expected_revision": None,
        },
    ).json()
    rejected = client.post(
        f"/api/v1/daily-entry/2026-03-30/planned-activities/"
        f"{walk['activities'][0]['id']}/confirm"
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "training_required"


def test_plan_and_actual_are_independent_and_deletion_sets_link_null(
    client: TestClient,
) -> None:
    plan = create_training(client, ["Atlas", "Aurora"])
    activity = plan["activities"][0]  # type: ignore[index]
    confirmed = client.post(
        f"/api/v1/daily-entry/2026-03-29/planned-activities/{activity['id']}/confirm"  # type: ignore[index]
    ).json()
    actual = confirmed["sessions"][0]
    update = actual_payload(["Atlas"], distance=5)
    update["expected_revision"] = actual["revision"]
    changed = client.patch(
        f"/api/v1/daily-entry/2026-03-29/sessions/{actual['id']}", json=update
    )
    assert changed.status_code == 200
    assert changed.json()["sessions"][0]["plan_status"] == "modified"
    assert changed.json()["sessions"][0]["deviations"] == [
        "Distance changed to 5 km",
        "1 planned dog did not run",
        "No saved planned lineup",
    ]
    still_planned = client.get("/api/v1/daily-plans/2026-03-29").json()
    assert len(still_planned["activities"][0]["participants"]) == 2

    deleted_plan = client.delete(
        f"/api/v1/daily-plans/2026-03-29/activities/{activity['id']}",  # type: ignore[index]
        params={"expected_revision": still_planned["revision"]},
    )
    assert deleted_plan.status_code == 200
    reopened = client.get("/api/v1/daily-entry/2026-03-29").json()
    assert reopened["sessions"][0]["source"] == "unlinked"
    assert reopened["sessions"][0]["planned_activity_id"] is None


@pytest.mark.parametrize(
    ("dog", "work_date", "distance", "reason"),
    [
        ("Nala", "2026-03-31", 10, "5 km only"),
        ("Sanchez", "2026-03-31", 5, "Junior"),
        ("Taro", "2026-03-31", 5, "Puppy"),
        ("Maple", "2025-12-25", 5, "Injured"),
        ("Koda", "2026-01-20", 5, "Rest"),
        ("Delta", "2026-02-05", 5, "Restricted"),
        ("Fjord", "2026-02-15", 5, "Retired"),
        ("Django", "2026-03-31", 5, "Archived"),
        ("Vega", "2026-01-31", 5, "Not yet born"),
    ],
)
def test_actual_effective_eligibility_rejections(
    client: TestClient, dog: str, work_date: str, distance: int, reason: str
) -> None:
    response = client.post(
        f"/api/v1/daily-entry/{work_date}/sessions",
        json=actual_payload([dog], distance=distance),
    )
    assert response.status_code == 422
    assert reason in response.json()["detail"]["message"]


def test_actual_distance_limit_allows_30_rejects_35_and_delete_frees_capacity(
    client: TestClient,
) -> None:
    created = []
    for index in range(3):
        response = client.post(
            "/api/v1/daily-entry/2026-03-29/sessions",
            json=actual_payload(["Atlas"], label=f"Run {index + 1}"),
        )
        assert response.status_code == 200, response.text
        created.append(response.json()["sessions"][-1])
    blocked = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json=actual_payload(["Atlas"], distance=5, label="Too far"),
    )
    assert blocked.status_code == 422
    assert "30 km" in blocked.json()["detail"]["message"]

    removed = client.delete(
        f"/api/v1/daily-entry/2026-03-29/sessions/{created[0]['id']}",
        params={"expected_revision": created[0]["revision"]},
    )
    assert removed.status_code == 200
    allowed = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json=actual_payload(["Atlas"], distance=5, label="Freed capacity"),
    )
    assert allowed.status_code == 200


@pytest.mark.parametrize(
    "distances",
    [
        [10, 10, 10],
        [10, 10, 5, 5],
        [10, 5, 5, 5, 5],
    ],
)
def test_canonical_actual_combinations_reach_exactly_30(
    client: TestClient, distances: list[int]
) -> None:
    latest: dict[str, object] | None = None
    for index, distance in enumerate(distances):
        response = client.post(
            "/api/v1/daily-entry/2026-03-29/sessions",
            json=actual_payload(
                ["Atlas"], distance=distance, label=f"Combination run {index + 1}"
            ),
        )
        assert response.status_code == 200, response.text
        latest = response.json()
    assert latest is not None
    atlas = next(
        dog
        for group in latest["housing_groups"]  # type: ignore[union-attr]
        for dog in group["dogs"]
        if dog["name"] == "Atlas"
    )
    assert atlas["actual_km"] == 30
    assert atlas["starts"] == len(distances)


def test_edit_to_35_is_rejected_and_linked_actual_delete_preserves_plan(
    client: TestClient,
) -> None:
    for label in ("First", "Second"):
        response = client.post(
            "/api/v1/daily-entry/2026-03-29/sessions",
            json=actual_payload(["Atlas"], label=label),
        )
        assert response.status_code == 200
    five = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json=actual_payload(["Atlas"], distance=5, label="Short"),
    ).json()["sessions"][-1]
    update = actual_payload(["Atlas"], distance=10, label="Would be 30")
    update["expected_revision"] = five["revision"]
    assert (
        client.patch(
            f"/api/v1/daily-entry/2026-03-29/sessions/{five['id']}", json=update
        ).status_code
        == 200
    )
    another_five = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json=actual_payload(["Aurora"], distance=5, label="Other dog"),
    ).json()["sessions"][-1]
    invalid = actual_payload(["Atlas"], distance=5, label="Would exceed")
    invalid["expected_revision"] = another_five["revision"]
    rejected = client.patch(
        f"/api/v1/daily-entry/2026-03-29/sessions/{another_five['id']}",
        json=invalid,
    )
    assert rejected.status_code == 422
    assert "30 km" in rejected.json()["detail"]["message"]

    with SessionLocal.begin() as session:
        reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
    plan = create_training(client, ["Atlas"])
    activity = plan["activities"][0]  # type: ignore[index]
    confirmed = client.post(
        f"/api/v1/daily-entry/2026-03-29/planned-activities/{activity['id']}/confirm"  # type: ignore[index]
    ).json()
    actual = confirmed["sessions"][0]
    removed = client.delete(
        f"/api/v1/daily-entry/2026-03-29/sessions/{actual['id']}",
        params={"expected_revision": actual["revision"]},
    )
    assert removed.status_code == 200
    assert removed.json()["planned_activities"][0]["actual_status"] == "not_recorded"
    assert (
        client.get("/api/v1/daily-plans/2026-03-29").json()["activities"][0]["id"]
        == activity["id"]
    )  # type: ignore[index]


def test_positioned_actual_enforces_role_and_hard_pair_conflict(
    client: TestClient,
) -> None:
    invalid_role = actual_payload(["Aurora"], distance=5)
    invalid_role["participants"] = [
        participant(
            "Aurora",
            assigned_role="lead",
            actual_team_sequence=1,
            pair_index=0,
            side="left",
            position_order=1,
        )
    ]
    response = client.post("/api/v1/daily-entry/2026-01-20/sessions", json=invalid_role)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "role_mismatch"

    conflict = actual_payload(["Atlas", "Fjord"], distance=5)
    conflict["participants"] = [
        participant(
            "Atlas",
            assigned_role="team",
            actual_team_sequence=1,
            pair_index=0,
            side="left",
            position_order=1,
        ),
        participant(
            "Fjord",
            assigned_role="team",
            actual_team_sequence=1,
            pair_index=0,
            side="right",
            position_order=2,
        ),
    ]
    rejected = client.post("/api/v1/daily-entry/2026-01-20/sessions", json=conflict)
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "hard_pair_conflict"

    unordered = client.post(
        "/api/v1/daily-entry/2026-01-20/sessions",
        json=actual_payload(["Atlas", "Fjord"], distance=5),
    )
    assert unordered.status_code == 200


def test_historical_housing_matches_kennel_map_across_move_boundary(
    client: TestClient,
) -> None:
    for selected_date, expected in (
        ("2026-01-14", {"Freya": "A1-01", "Atlas": "A1-02"}),
        ("2026-01-15", {"Freya": "A1-02", "Atlas": "A1-01"}),
    ):
        entry = client.get(f"/api/v1/daily-entry/{selected_date}").json()
        overview = {
            dog["name"]: group["code"]
            for group in entry["housing_groups"]
            for dog in group["dogs"]
        }
        map_snapshot = client.get(
            "/api/v1/kennel-map", params={"date": selected_date}
        ).json()
        map_housing = {
            resident["name"]: location["code"]
            for location in map_snapshot["locations"]
            for resident in location["residents"]
        }
        for name, location in expected.items():
            assert overview[name] == map_housing[name] == location


def test_not_run_is_ledger_free_and_can_be_reopened(client: TestClient) -> None:
    plan = create_training(client, ["Atlas"])
    activity_id = plan["activities"][0]["id"]  # type: ignore[index]
    base = f"/api/v1/daily-entry/2026-03-29/planned-activities/{activity_id}/not-run"
    marked = client.post(base)
    assert marked.status_code == 200
    assert marked.json()["planned_activities"][0]["actual_status"] == "not_run"
    assert marked.json()["sessions"] == []
    cleared = client.delete(base)
    assert cleared.status_code == 200
    assert cleared.json()["planned_activities"][0]["actual_status"] == "not_recorded"


def test_reset_restores_mutated_actual_ledger_and_baseline_checksum(
    client: TestClient,
) -> None:
    with SessionLocal() as session:
        assert semantic_checksum(session) == BASELINE_CHECKSUM
    response = client.post(
        "/api/v1/daily-entry/2026-03-29/sessions",
        json=actual_payload(["Atlas"], distance=5),
    )
    assert response.status_code == 200
    create_training(client, ["Aurora"])
    with SessionLocal() as session:
        assert semantic_checksum(session) != BASELINE_CHECKSUM
    with SessionLocal.begin() as session:
        reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
        assert semantic_checksum(session) == BASELINE_CHECKSUM
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DailyPlan)) == 0
        assert session.scalar(select(func.count()).select_from(PlannedTeam)) == 0
        assert session.scalar(select(func.count()).select_from(WorkSession)) == 140
