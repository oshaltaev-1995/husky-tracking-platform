from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.service import reset_demo_world
from app.main import app
from app.models import Dog


@pytest.fixture(scope="module", autouse=True)
def canonical_demo_world() -> Iterator[None]:
    with SessionLocal.begin() as session:
        reset_demo_world(
            session,
            DemoClock.from_settings(get_settings()),
            require_enabled=False,
        )
    yield


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def dog_id(name: str) -> str:
    with SessionLocal() as session:
        public_id = session.scalar(select(Dog.public_id).where(Dog.name == name))
    assert public_id is not None
    return str(public_id)


def test_registry_returns_active_population_and_supports_search(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/dogs")
    assert response.status_code == 200
    body = response.json()
    assert body["result_count"] == body["summary"]["total"] == 50
    assert body["summary"] == {
        "total": 50,
        "puppy": 10,
        "junior": 6,
        "training": 8,
        "standard": 26,
    }
    assert all(item["state"]["lifecycle"] == "active" for item in body["items"])

    by_name = client.get("/api/v1/dogs", params={"search": "aUrOrA"}).json()
    assert [item["name"] for item in by_name["items"]] == ["Aurora"]

    by_location = client.get("/api/v1/dogs", params={"search": "a1-01"}).json()
    assert {item["name"] for item in by_location["items"]} == {"Atlas", "Aurora"}


def test_registry_domain_filters_combine_and_sort(client: TestClient) -> None:
    puppies = client.get("/api/v1/dogs", params={"dog_class": "puppy"}).json()
    assert puppies["result_count"] == 10
    assert {item["state"]["dog_class"] for item in puppies["items"]} == {"puppy"}

    retired = client.get("/api/v1/dogs", params={"availability": "retired"}).json()
    assert {item["name"] for item in retired["items"]} == {"Fjord"}

    combined = client.get(
        "/api/v1/dogs",
        params={
            "sex": "female",
            "neutered": "true",
            "housing": "A1",
            "capability": "team",
        },
    ).json()
    assert combined["result_count"] > 0
    assert all(item["sex"] == "female" for item in combined["items"])
    assert all(item["is_neutered"] for item in combined["items"])
    assert all(item["state"]["housing"]["zone"] == "A" for item in combined["items"])
    assert all(item["state"]["housing"]["row"] == "1" for item in combined["items"])
    assert all("team" in item["capabilities"] for item in combined["items"])

    oldest = client.get("/api/v1/dogs", params={"sort": "oldest"}).json()["items"]
    youngest = client.get("/api/v1/dogs", params={"sort": "youngest"}).json()["items"]
    assert oldest[0]["birth_date"] <= oldest[-1]["birth_date"]
    assert youngest[0]["birth_date"] >= youngest[-1]["birth_date"]
    assert (
        client.get("/api/v1/dogs", params={"dog_class": "invalid"}).status_code == 422
    )


def test_archive_returns_only_archived_dogs_and_reason_filters(
    client: TestClient,
) -> None:
    archive = client.get("/api/v1/archive").json()
    assert archive["result_count"] == archive["total_archived"] == 10
    names = {item["name"] for item in archive["items"]}
    assert "Django" in names
    assert "Aurora" not in names

    expected = {"euthanized": 3, "deceased": 3, "rehomed_to_guide": 4}
    for reason, count in expected.items():
        response = client.get("/api/v1/archive", params={"reason": reason}).json()
        assert response["result_count"] == count
        assert {item["archive"]["reason"] for item in response["items"]} == {reason}

    search = client.get("/api/v1/archive", params={"search": "django"}).json()
    assert [item["name"] for item in search["items"]] == ["Django"]


def test_profiles_resolve_current_state_at_demo_reference_date(
    client: TestClient,
) -> None:
    aurora = client.get(f"/api/v1/dogs/{dog_id('Aurora')}").json()
    assert aurora["state"] == {
        "reference_date": "2026-03-31",
        "lifecycle": "active",
        "dog_class": "standard",
        "class_is_historical": False,
        "availability": "available",
        "housing": {
            "code": "A1-01",
            "display_name": "A1 enclosure 1",
            "location_type": "adult_enclosure",
            "zone": "A",
            "row": "1",
        },
    }
    assert aurora["age_label"] == "10 years, 2 months"

    django = client.get(f"/api/v1/dogs/{dog_id('Django')}").json()
    assert django["state"]["lifecycle"] == "archived"
    assert django["state"]["housing"] is None
    assert django["last_known_housing"] is not None
    assert django["archive"]["archive_date"] == "2025-12-15"


def test_pedigree_uses_litters_and_keeps_archived_relatives(client: TestClient) -> None:
    nova = client.get(f"/api/v1/dogs/{dog_id('Nova')}/pedigree").json()
    assert nova["mother"]["name"] == "Hazel"
    assert nova["father"]["name"] == "Koda"
    assert nova["maternal_grandparents"]["mother"]["name"] == "Aurora"
    assert nova["paternal_grandparents"]["father"] == {
        "id": dog_id("Django"),
        "name": "Django",
        "birth_date": "2019-01-02",
        "lifecycle": "archived",
        "dog_class": "standard",
    }
    assert {litter["code"] for litter in nova["offspring"]} == {"T"}
    assert len(nova["offspring"][0]["children"]) == 5

    sanchez = client.get(f"/api/v1/dogs/{dog_id('Sanchez')}/pedigree").json()
    assert sanchez["litter"]["code"] == "S"
    assert len(sanchez["litter"]["siblings"]) == 7
    assert sanchez["father"]["name"] == "Nimbus"
    assert sanchez["father"]["lifecycle"] == "archived"


def test_work_totals_zero_states_and_interruptions(client: TestClient) -> None:
    aurora = client.get(f"/api/v1/dogs/{dog_id('Aurora')}/work").json()
    assert aurora["summary"]["total_km"] == sum(
        entry["distance_km"] for entry in aurora["entries"]
    )
    assert aurora["summary"]["starts"] == len(aurora["entries"])
    assert aurora["summary"]["starts"] == (
        aurora["summary"]["starts_5km"] + aurora["summary"]["starts_10km"]
    )

    puppy = client.get(f"/api/v1/dogs/{dog_id('Taro')}/work").json()
    assert puppy["summary"]["starts"] == 0
    assert puppy["entries"] == puppy["weekly"] == []

    maple = client.get(f"/api/v1/dogs/{dog_id('Maple')}/work").json()
    maple_dates = {date.fromisoformat(entry["date"]) for entry in maple["entries"]}
    assert not any(date(2025, 12, 20) <= row < date(2026, 1, 10) for row in maple_dates)

    fjord = client.get(f"/api/v1/dogs/{dog_id('Fjord')}/work").json()
    assert all(entry["date"] < "2026-02-15" for entry in fjord["entries"])


def test_history_is_effective_ordered_and_includes_archive_metadata(
    client: TestClient,
) -> None:
    maple = client.get(f"/api/v1/dogs/{dog_id('Maple')}/history").json()
    assert [item["valid_from"] for item in maple["availability"]] == sorted(
        item["valid_from"] for item in maple["availability"]
    )
    assert "injured" in {item["value"] for item in maple["availability"]}
    assert maple["classes"] and maple["housing"] and maple["lifecycle"]

    django = client.get(f"/api/v1/dogs/{dog_id('Django')}/history").json()
    assert django["archive"]["reason"] == "euthanized"
    assert django["lifecycle"][-1]["value"] == "archived"
    assert django["lifecycle"][-1]["is_current"] is True


def test_missing_and_malformed_dogs_return_application_errors(
    client: TestClient,
) -> None:
    assert (
        client.get("/api/v1/dogs/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )
    assert client.get("/api/v1/dogs/not-a-uuid").status_code == 422
