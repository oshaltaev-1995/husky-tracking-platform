from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.service import reset_demo_world
from app.main import app
from app.models import DailyPlan, Dog, WorkParticipation, WorkSession


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


def dog_id(name: str) -> str:
    with SessionLocal() as session:
        public_id = session.scalar(select(Dog.public_id).where(Dog.name == name))
    assert public_id is not None
    return str(public_id)


def activity_payload(
    dog: str,
    *,
    activity_type: str = "training",
    distance_km: int | None = 10,
    expected_revision: int | None = None,
    title: str = "Forest Loop",
) -> dict[str, object]:
    return {
        "activity_type": activity_type,
        "start_time": "09:15:00",
        "title": title,
        "distance_km": distance_km,
        "notes": "Synthetic planning note.",
        "participant_ids": [dog_id(dog)],
        "expected_revision": expected_revision,
    }


def create_activity(
    client: TestClient,
    plan_date: str,
    dog: str,
    *,
    distance_km: int = 10,
    expected_revision: int | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/daily-plans/{plan_date}/activities",
        json=activity_payload(
            dog,
            distance_km=distance_km,
            expected_revision=expected_revision,
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()


def candidate(
    client: TestClient, plan_date: str, dog: str, **params: object
) -> dict[str, object]:
    response = client.get(
        f"/api/v1/daily-plans/{plan_date}/eligible-dogs", params=params
    )
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["dogs"] if item["name"] == dog)


def test_empty_day_is_lazy_and_date_bounds_are_enforced(client: TestClient) -> None:
    response = client.get("/api/v1/daily-plans/2026-03-31")
    assert response.status_code == 200
    assert response.json() == {
        "selected_date": "2026-03-31",
        "season_start": "2025-12-01",
        "season_end": "2026-03-31",
        "reference_date": "2026-03-31",
        "exists": False,
        "id": None,
        "revision": None,
        "notes": None,
        "activities": [],
    }
    assert client.get("/api/v1/daily-plans/2025-11-30").status_code == 422
    assert client.get("/api/v1/daily-plans/2026-04-01").status_code == 422


def test_create_edit_delete_and_unique_plan_round_trip(client: TestClient) -> None:
    plan = create_activity(client, "2026-03-31", "Atlas")
    assert plan["exists"] is True
    assert plan["revision"] == 1
    assert plan["activities"][0]["participants"][0] == {
        "id": dog_id("Atlas"),
        "name": "Atlas",
        "housing_code": "A1-01",
        "dog_class": "standard",
        "availability": "available",
    }

    activity = plan["activities"][0]
    payload = activity_payload(
        "Aurora", distance_km=5, expected_revision=1, title="River Trail"
    )
    payload["start_time"] = "10:30:00"
    response = client.patch(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}",
        json=payload,
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["revision"] == 2
    assert updated["activities"][0]["title"] == "River Trail"
    assert updated["activities"][0]["distance_km"] == 5
    assert updated["activities"][0]["start_time"] == "10:30:00"

    noted = client.put(
        "/api/v1/daily-plans/2026-03-31",
        json={"notes": "Cold morning; check trail surface.", "expected_revision": 2},
    )
    assert noted.status_code == 200
    assert noted.json()["notes"] == "Cold morning; check trail surface."

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DailyPlan)) == 1

    deleted = client.delete(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity['id']}",
        params={"expected_revision": 3},
    )
    assert deleted.status_code == 200
    assert deleted.json()["activities"] == []
    assert deleted.json()["notes"] == "Cold morning; check trail surface."


def test_deleting_last_activity_removes_a_meaningless_empty_plan(
    client: TestClient,
) -> None:
    plan = create_activity(client, "2026-03-31", "Atlas")
    activity_id = plan["activities"][0]["id"]
    response = client.delete(
        f"/api/v1/daily-plans/2026-03-31/activities/{activity_id}",
        params={"expected_revision": plan["revision"]},
    )
    assert response.status_code == 200
    assert response.json()["exists"] is False
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(DailyPlan)) == 0


def test_activity_ordering_is_stable_and_mutable(client: TestClient) -> None:
    first = create_activity(client, "2026-03-31", "Atlas")
    second = create_activity(
        client, "2026-03-31", "Aurora", expected_revision=first["revision"]
    )
    activities = second["activities"]
    response = client.post(
        f"/api/v1/daily-plans/2026-03-31/activities/{activities[1]['id']}/move",
        json={"direction": "up", "expected_revision": second["revision"]},
    )
    assert response.status_code == 200
    reordered = response.json()["activities"]
    assert [item["sequence"] for item in reordered] == [1, 2]
    assert reordered[0]["participants"][0]["name"] == "Aurora"


def test_editing_keeps_an_existing_participant_without_duplicate_rows(
    client: TestClient,
) -> None:
    plan = create_activity(client, "2026-03-31", "Atlas")
    current = plan["activities"][0]
    response = client.patch(
        f"/api/v1/daily-plans/2026-03-31/activities/{current['id']}",
        json=activity_payload(
            "Atlas",
            distance_km=5,
            expected_revision=plan["revision"],
            title="Short Forest Loop",
        ),
    )
    assert response.status_code == 200, response.text
    updated = response.json()["activities"][0]
    assert updated["title"] == "Short Forest Loop"
    assert [dog["name"] for dog in updated["participants"]] == ["Atlas"]


@pytest.mark.parametrize(
    ("dog", "distance_km", "expected_reason"),
    [
        ("Nala", 10, "Training class · 5 km only"),
        ("Sanchez", 5, "Junior"),
        ("Taro", 5, "Puppy"),
        ("Hazel", 5, "Injured"),
        ("Orion", 5, "Rest"),
        ("Cedar", 5, "Restricted"),
        ("Fjord", 5, "Retired"),
        ("Django", 5, "Archived"),
    ],
)
def test_training_eligibility_explains_domain_rejections(
    client: TestClient, dog: str, distance_km: int, expected_reason: str
) -> None:
    result = candidate(
        client,
        "2026-03-31",
        dog,
        activity_type="training",
        distance_km=distance_km,
    )
    assert result["eligible"] is False
    assert result["reasons"] == [expected_reason]
    rejected = client.post(
        "/api/v1/daily-plans/2026-03-31/activities",
        json=activity_payload(dog, distance_km=distance_km),
    )
    assert rejected.status_code == 422
    assert expected_reason in rejected.json()["detail"]["message"]


def test_standard_and_training_class_distance_rules_are_authoritative(
    client: TestClient,
) -> None:
    assert candidate(
        client,
        "2026-03-31",
        "Atlas",
        activity_type="training",
        distance_km=5,
    )["eligible"]
    assert candidate(
        client,
        "2026-03-31",
        "Atlas",
        activity_type="training",
        distance_km=10,
    )["eligible"]
    assert candidate(
        client,
        "2026-03-31",
        "Nala",
        activity_type="training",
        distance_km=5,
    )["eligible"]

    invalid = client.post(
        "/api/v1/daily-plans/2026-03-31/activities",
        json=activity_payload("Nala", distance_km=10),
    )
    assert invalid.status_code == 422
    assert "5 km only" in invalid.json()["detail"]["message"]


def test_effective_state_uses_plan_date_for_injury_retirement_and_birth(
    client: TestClient,
) -> None:
    assert candidate(
        client,
        "2025-12-25",
        "Maple",
        activity_type="open_space_walk",
    )["reasons"] == ["Injured"]
    assert candidate(
        client,
        "2026-01-10",
        "Maple",
        activity_type="open_space_walk",
    )["eligible"]
    assert candidate(
        client,
        "2026-02-14",
        "Fjord",
        activity_type="individual_exercise",
    )["eligible"]
    assert candidate(
        client,
        "2026-02-15",
        "Fjord",
        activity_type="individual_exercise",
    )["reasons"] == ["Retired"]
    assert candidate(
        client,
        "2026-01-31",
        "Vega",
        activity_type="open_space_walk",
    )["reasons"] == ["Not yet born"]
    unborn = client.post(
        "/api/v1/daily-plans/2026-01-31/activities",
        json=activity_payload(
            "Vega",
            activity_type="open_space_walk",
            distance_km=None,
            title="Puppy walk",
        ),
    )
    assert unborn.status_code == 422
    assert "Not yet born" in unborn.json()["detail"]["message"]


def test_daily_training_limit_accepts_30_rejects_35_and_delete_frees_capacity(
    client: TestClient,
) -> None:
    plan = create_activity(client, "2026-03-31", "Atlas")
    plan = create_activity(
        client, "2026-03-31", "Atlas", expected_revision=plan["revision"]
    )
    plan = create_activity(
        client, "2026-03-31", "Atlas", expected_revision=plan["revision"]
    )
    assert candidate(
        client,
        "2026-03-31",
        "Atlas",
        activity_type="training",
        distance_km=5,
    )["reasons"] == ["30 km daily limit reached"]

    too_far = client.post(
        "/api/v1/daily-plans/2026-03-31/activities",
        json=activity_payload(
            "Atlas", distance_km=5, expected_revision=plan["revision"]
        ),
    )
    assert too_far.status_code == 422
    assert "30 km" in too_far.json()["detail"]["message"]

    removed = client.delete(
        f"/api/v1/daily-plans/2026-03-31/activities/{plan['activities'][0]['id']}",
        params={"expected_revision": plan["revision"]},
    )
    after_delete = removed.json()
    added = create_activity(
        client,
        "2026-03-31",
        "Atlas",
        distance_km=5,
        expected_revision=after_delete["revision"],
    )
    assert (
        sum(
            item["distance_km"]
            for item in added["activities"]
            if item["activity_type"] == "training"
        )
        == 25
    )


@pytest.mark.parametrize(
    ("activity_type", "dog", "plan_date"),
    [
        ("open_space_walk", "Taro", "2026-03-31"),
        ("individual_exercise", "Sanchez", "2026-03-31"),
        ("rest", "Maple", "2025-12-25"),
    ],
)
def test_non_sled_activity_participants_and_no_distance(
    client: TestClient, activity_type: str, dog: str, plan_date: str
) -> None:
    response = client.post(
        f"/api/v1/daily-plans/{plan_date}/activities",
        json=activity_payload(
            dog,
            activity_type=activity_type,
            distance_km=None,
            title=activity_type.replace("_", " ").title(),
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["activities"][0]["distance_km"] is None


def test_duplicate_participant_and_unsupported_distance_are_rejected(
    client: TestClient,
) -> None:
    payload = activity_payload("Atlas")
    payload["participant_ids"] = [dog_id("Atlas"), dog_id("Atlas")]
    assert (
        client.post(
            "/api/v1/daily-plans/2026-03-31/activities", json=payload
        ).status_code
        == 422
    )
    payload = activity_payload("Atlas")
    payload["distance_km"] = 15
    assert (
        client.post(
            "/api/v1/daily-plans/2026-03-31/activities", json=payload
        ).status_code
        == 422
    )


def test_stale_mutation_conflicts_and_actual_work_is_untouched(
    client: TestClient,
) -> None:
    with SessionLocal() as session:
        before = session.scalar(
            select(func.count())
            .select_from(WorkParticipation)
            .join(WorkSession)
            .where(WorkSession.demo_workspace_id.is_(None))
        )
    plan = create_activity(client, "2026-03-31", "Atlas")
    stale = client.put(
        "/api/v1/daily-plans/2026-03-31",
        json={"notes": "Stale", "expected_revision": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "plan_changed"
    with SessionLocal() as session:
        after = session.scalar(
            select(func.count())
            .select_from(WorkParticipation)
            .join(WorkSession)
            .where(WorkSession.demo_workspace_id.is_(None))
        )
    assert before == after == 1120
    assert plan["revision"] == 1
