from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal, engine
from app.demo.service import reset_demo_world
from app.main import app
from app.models import Dog
from app.services.effective_state import EffectiveDogState
from app.services.kennel_map_read_service import KennelMapReadService


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


def residents_by_name(body: dict[str, object]) -> dict[str, dict[str, object]]:
    residents: dict[str, dict[str, object]] = {}
    for location in body["locations"]:  # type: ignore[index,union-attr]
        for resident in location["residents"]:
            residents[resident["name"]] = {
                **resident,
                "location_code": location["code"],
            }
    return residents


def test_default_snapshot_has_canonical_topology_and_occupancy(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/kennel-map")
    assert response.status_code == 200
    body = response.json()
    assert body["selected_date"] == body["reference_date"] == "2026-03-31"
    assert body["summary"] == {
        "resident_dogs": 50,
        "occupied_locations": 22,
        "unavailable_dogs": 4,
        "class_counts": {
            "junior": 6,
            "puppy": 10,
            "standard": 26,
            "training": 8,
        },
        "sex_counts": {"female": 22, "male": 28},
        "neutered_counts": {"intact": 28, "neutered": 22},
        "availability_counts": {
            "available": 46,
            "injured": 1,
            "rest": 1,
            "restricted": 1,
            "retired": 1,
        },
    }

    adult = [
        location
        for location in body["locations"]
        if location["location_type"] == "adult_enclosure"
    ]
    puppy = [
        location
        for location in body["locations"]
        if location["location_type"] == "puppy_area"
    ]
    assert [location["code"] for location in adult] == [
        f"{zone}{row}-{position:02d}"
        for zone in "AB"
        for row in "12"
        for position in range(1, 6)
    ]
    assert len(adult) == 20
    assert all(
        location["capacity"] == 2 and len(location["residents"]) == 2
        for location in adult
    )
    assert [location["code"] for location in puppy] == ["PUPPY-A", "PUPPY-B"]
    assert all(
        location["capacity"] == 5 and len(location["residents"]) == 5
        for location in puppy
    )


def test_historical_snapshot_crosses_housing_move_boundary(
    client: TestClient,
) -> None:
    before = residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": "2026-01-14"}).json()
    )
    after = residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": "2026-01-15"}).json()
    )

    assert before["Freya"]["location_code"] == "A1-01"
    assert after["Freya"]["location_code"] == "A1-02"
    assert before["Atlas"]["location_code"] == "A1-02"
    assert after["Atlas"]["location_code"] == "A1-01"


@pytest.mark.parametrize(
    ("dog", "during", "expected", "outside", "outside_expected"),
    [
        ("Maple", "2025-12-25", "injured", "2026-01-10", "available"),
        ("Koda", "2026-01-20", "rest", "2026-01-25", "available"),
        ("Delta", "2026-02-05", "restricted", "2026-02-12", "available"),
        ("Fjord", "2026-02-15", "retired", "2026-02-14", "available"),
        ("Aurora", "2026-03-06", "rest", "2026-03-10", "available"),
    ],
)
def test_historical_snapshot_resolves_availability_boundaries(
    client: TestClient,
    dog: str,
    during: str,
    expected: str,
    outside: str,
    outside_expected: str,
) -> None:
    during_residents = residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": during}).json()
    )
    outside_residents = residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": outside}).json()
    )
    assert during_residents[dog]["availability"] == expected
    assert outside_residents[dog]["availability"] == outside_expected


def test_historical_snapshot_resolves_class_and_birth_boundaries(
    client: TestClient,
) -> None:
    january = client.get("/api/v1/kennel-map", params={"date": "2026-01-31"}).json()
    february = client.get("/api/v1/kennel-map", params={"date": "2026-02-01"}).json()
    january_residents = residents_by_name(january)
    february_residents = residents_by_name(february)
    assert january_residents["Nora"]["dog_class"] == "training"
    assert february_residents["Nora"]["dog_class"] == "standard"

    assert january["summary"]["resident_dogs"] == 45
    assert "Vega" not in january_residents
    assert "Vega" in residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": "2026-02-18"}).json()
    )


def test_archived_lifecycle_is_historical_but_housing_gaps_remain_gaps(
    client: TestClient,
) -> None:
    with SessionLocal() as session:
        django = session.scalar(
            select(Dog)
            .where(Dog.name == "Django")
            .options(selectinload(Dog.lifecycle_periods))
        )
        assert django is not None
        assert EffectiveDogState(date(2025, 12, 14)).lifecycle(django) == "active"
        assert EffectiveDogState(date(2025, 12, 15)).lifecycle(django) == "archived"

    before = residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": "2025-12-14"}).json()
    )
    after = residents_by_name(
        client.get("/api/v1/kennel-map", params={"date": "2025-12-15"}).json()
    )
    assert "Django" not in before
    assert "Django" not in after


def test_profile_linkage_and_current_projection_are_consistent(
    client: TestClient,
) -> None:
    snapshot = residents_by_name(client.get("/api/v1/kennel-map").json())
    aurora = snapshot["Aurora"]
    profile = client.get(f"/api/v1/dogs/{aurora['id']}").json()
    assert profile["id"] == aurora["id"]
    assert profile["state"]["housing"]["code"] == aurora["location_code"]
    assert profile["state"]["dog_class"] == aurora["dog_class"]
    assert profile["state"]["availability"] == aurora["availability"]


def test_map_query_is_bounded_and_does_not_scale_per_location() -> None:
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
            snapshot = KennelMapReadService(
                session, DemoClock.from_settings(get_settings())
            ).snapshot(date(2026, 3, 31))
            assert snapshot.summary.resident_dogs == 50
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert len(statements) <= 8


@pytest.mark.parametrize("value", ["not-a-date", "2025-11-30", "2026-04-01"])
def test_invalid_and_out_of_range_dates_return_422(
    client: TestClient, value: str
) -> None:
    response = client.get("/api/v1/kennel-map", params={"date": value})
    assert response.status_code == 422
