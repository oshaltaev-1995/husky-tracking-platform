from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.service import reset_demo_world
from app.main import app
from app.models import (
    Dog,
    PlannedTeam,
    PlannedTeamSlot,
    WorkParticipation,
    WorkSession,
)

MULTI_ROLE = ["Atlas", "Daisy", "Freya", "Kenzo", "Milo", "Otis"]
POOL_16 = [
    *MULTI_ROLE,
    "Clover",
    "Drift",
    "Dune",
    "Harbor",
    "Hugo",
    "Kira",
    "Koda",
    "Magnus",
    "North",
    "Opal",
]


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


def create_training(
    client: TestClient,
    names: list[str],
    *,
    plan_date: str = "2026-03-31",
    distance: int = 5,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/daily-plans/{plan_date}/activities",
        json={
            "activity_type": "training",
            "start_time": "09:00:00",
            "title": "Forest Loop",
            "distance_km": distance,
            "notes": None,
            "participant_ids": dog_ids(*names),
            "expected_revision": None,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def generate(
    client: TestClient,
    plan: dict[str, object],
    *,
    plan_date: str = "2026-03-31",
    team_count: int,
    team_size: int,
):
    activity = plan["activities"][0]  # type: ignore[index]
    return client.post(
        f"/api/v1/daily-plans/{plan_date}/activities/{activity['id']}/teams/generate",  # type: ignore[index]
        json={"team_count": team_count, "team_size": team_size},
    )


def save_payload(generated: dict[str, object], revision: int, *, replace=False):
    teams = []
    for team in generated["teams"]:  # type: ignore[union-attr]
        teams.append(
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
        )
    return {
        "expected_revision": revision,
        "replace_existing": replace,
        "teams": teams,
    }


@pytest.mark.parametrize(
    ("names", "team_count", "team_size"),
    [
        (MULTI_ROLE[:4], 1, 4),
        (MULTI_ROLE, 1, 6),
        (POOL_16[:8], 1, 8),
        (POOL_16, 2, 8),
        (POOL_16 + ["Olive", "Niko"], 3, 6),
    ],
)
def test_solver_generates_supported_deterministic_geometry(
    client: TestClient, names: list[str], team_count: int, team_size: int
) -> None:
    plan = create_training(client, names)
    first = generate(client, plan, team_count=team_count, team_size=team_size)
    second = generate(client, plan, team_count=team_count, team_size=team_size)
    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    teams = first.json()["teams"]
    assert len(teams) == team_count
    assert all(len(team["slots"]) == team_size for team in teams)
    for team in teams:
        assert {slot["side"] for slot in team["slots"]} == {"left", "right"}
        assert [slot["harness_role"] for slot in team["slots"][:2]] == [
            "lead",
            "lead",
        ]
        assert [slot["harness_role"] for slot in team["slots"][-2:]] == [
            "wheel",
            "wheel",
        ]


def test_context_is_bounded_to_selected_pool_and_recommends_exact_fit(
    client: TestClient,
) -> None:
    plan = create_training(client, MULTI_ROLE + ["Clover", "Drift"])
    activity = plan["activities"][0]
    response = client.get(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/team-builder"
    )
    assert response.status_code == 200
    context = response.json()
    assert context["recommended_team_count"] == 1
    assert context["recommended_team_size"] == 8
    assert len(context["candidates"]) == 8
    assert context["capability_summary"]["lead"] >= 2
    assert context["activity"]["plan_revision"] == 1


def test_structured_role_and_pool_shortages(client: TestClient) -> None:
    no_roles = create_training(client, ["Aurora", "Cosmo", "Halo", "Kaia"])
    lead = generate(client, no_roles, team_count=1, team_size=4)
    assert lead.status_code == 422
    assert lead.json()["detail"]["code"] == "lead_shortage"

    too_small = create_training(client, MULTI_ROLE[:4], plan_date="2026-03-30")
    pool = generate(
        client,
        too_small,
        plan_date="2026-03-30",
        team_count=2,
        team_size=4,
    )
    assert pool.status_code == 422
    assert pool.json()["detail"]["code"] == "insufficient_pool"


def test_small_training_remains_valid_without_a_harness_lineup(
    client: TestClient,
) -> None:
    plan = create_training(client, MULTI_ROLE[:2])
    assert plan["minimum_team_size"] == 4
    activity = plan["activities"][0]
    context = client.get(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/team-builder"
    )
    assert context.status_code == 200
    assert context.json()["supported_team_sizes"][0] == plan["minimum_team_size"]
    assert context.json()["activity"]["participant_count"] == 2
    result = generate(client, plan, team_count=1, team_size=4)
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "insufficient_pool"


def test_save_round_trip_revision_summary_and_replace_protection(
    client: TestClient,
) -> None:
    plan = create_training(client, POOL_16)
    activity = plan["activities"][0]
    generated = generate(client, plan, team_count=2, team_size=8).json()
    url = f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/teams"
    saved = client.put(url, json=save_payload(generated, 1))
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["saved_teams"]) == 2
    assert saved.json()["activity"]["plan_revision"] == 2

    reopened = client.get(url.replace("/teams", "/team-builder"))
    assert reopened.status_code == 200
    assert reopened.json()["saved_teams"] == saved.json()["saved_teams"]

    daily = client.get("/api/v1/daily-plans/2026-03-31").json()
    assert daily["activities"][0]["team_count"] == 2
    assert daily["activities"][0]["arranged_dog_count"] == 16

    conflict = client.put(url, json=save_payload(generated, 2))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "saved_teams_require_replace"

    replaced = client.put(url, json=save_payload(generated, 2, replace=True))
    assert replaced.status_code == 200
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(PlannedTeam)) == 2
        assert session.scalar(select(func.count()).select_from(PlannedTeamSlot)) == 16


def test_manual_save_rejects_role_mismatch_and_allows_soft_pair_separation(
    client: TestClient,
) -> None:
    names = [*MULTI_ROLE[:4], "Aurora"]
    plan = create_training(client, names)
    generated = generate(client, plan, team_count=1, team_size=4).json()
    payload = save_payload(generated, 1)
    payload["teams"][0]["slots"][0]["dog_id"] = dog_ids("Aurora")[0]
    activity = plan["activities"][0]
    response = client.put(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/teams",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "role_mismatch"


def test_manual_save_rejects_ambiguous_position_order(client: TestClient) -> None:
    plan = create_training(client, MULTI_ROLE[:4])
    activity = plan["activities"][0]
    generated = generate(client, plan, team_count=1, team_size=4).json()
    payload = save_payload(generated, 1)
    payload["teams"][0]["slots"][0]["position_order"] = 2
    response = client.put(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/teams",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_geometry"


def test_hard_conflict_blocks_only_same_harness_pair(client: TestClient) -> None:
    names = ["Atlas", "Fjord", "Daisy", "Freya", "Kenzo", "Milo"]
    plan = create_training(client, names, plan_date="2026-01-20")
    generated = generate(
        client,
        plan,
        plan_date="2026-01-20",
        team_count=1,
        team_size=6,
    ).json()
    payload = save_payload(generated, 1)
    atlas, fjord, daisy, freya, kenzo, milo = dog_ids(
        "Atlas", "Fjord", "Daisy", "Freya", "Kenzo", "Milo"
    )
    team_slots = payload["teams"][0]["slots"]
    assignments = {
        "lead": iter((daisy, freya)),
        "team": iter((atlas, fjord)),
        "wheel": iter((kenzo, milo)),
    }
    for slot in team_slots:
        slot["dog_id"] = next(assignments[slot["harness_role"]])
    activity = plan["activities"][0]
    response = client.put(
        f"/api/v1/daily-plans/2026-01-20/activities/{activity['id']}/teams",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "hard_pair_conflict"
    assert "Cannot pair Atlas with Fjord" in response.json()["detail"]["message"]


def test_non_training_activity_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/daily-plans/2026-03-31/activities",
        json={
            "activity_type": "rest",
            "start_time": None,
            "title": "Rest",
            "distance_km": None,
            "notes": None,
            "participant_ids": dog_ids("Atlas"),
            "expected_revision": None,
        },
    )
    activity = response.json()["activities"][0]
    builder = client.get(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/team-builder"
    )
    assert builder.status_code == 422
    assert builder.json()["detail"]["code"] == "training_required"


def test_future_actual_work_cannot_change_historical_generation(
    client: TestClient,
) -> None:
    plan_date = "2026-01-20"
    plan = create_training(client, MULTI_ROLE, plan_date=plan_date)
    before = generate(
        client, plan, plan_date=plan_date, team_count=1, team_size=6
    ).json()
    with SessionLocal.begin() as session:
        atlas_id = session.scalar(select(Dog.id).where(Dog.name == "Atlas"))
        assert atlas_id is not None
        work = WorkSession(
            source_reference="p6-future-proof",
            work_date=date(2026, 3, 30),
            distance_km=10,
            activity_type="sled_training",
            label="Future fixture",
        )
        session.add(work)
        session.flush()
        session.add(WorkParticipation(session_id=work.id, dog_id=atlas_id))
    after = generate(
        client, plan, plan_date=plan_date, team_count=1, team_size=6
    ).json()
    assert before == after


def test_activity_change_requires_explicit_transactional_lineup_clear(
    client: TestClient,
) -> None:
    plan = create_training(client, POOL_16[:8])
    activity = plan["activities"][0]
    generated = generate(client, plan, team_count=1, team_size=8).json()
    url = f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}"
    saved = client.put(f"{url}/teams", json=save_payload(generated, 1)).json()
    update = {
        "activity_type": "training",
        "start_time": "09:00:00",
        "title": "Short Loop",
        "distance_km": 5,
        "notes": None,
        "participant_ids": dog_ids(*POOL_16[:2]),
        "expected_revision": saved["activity"]["plan_revision"],
    }
    blocked = client.patch(url, json=update)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "saved_teams_require_clear"
    update["clear_saved_teams"] = True
    cleared = client.patch(url, json=update)
    assert cleared.status_code == 200
    assert cleared.json()["activities"][0]["team_count"] == 0
    assert len(cleared.json()["activities"][0]["participants"]) == 2
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(PlannedTeam)) == 0


def test_deleting_activity_and_reset_clear_workspace_without_deleting_dogs(
    client: TestClient,
) -> None:
    plan = create_training(client, MULTI_ROLE[:4])
    activity = plan["activities"][0]
    generated = generate(client, plan, team_count=1, team_size=4).json()
    saved = client.put(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}/teams",
        json=save_payload(generated, 1),
    ).json()
    deleted = client.delete(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}",
        params={"expected_revision": saved["activity"]["plan_revision"]},
    )
    assert deleted.status_code == 200
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(PlannedTeam)) == 0
        assert session.scalar(select(func.count()).select_from(Dog)) == 60

    with SessionLocal.begin() as session:
        checksum = reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
    assert (
        checksum == "2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2"
    )
