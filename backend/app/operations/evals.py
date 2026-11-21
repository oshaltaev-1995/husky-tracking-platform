"""Small offline rule/evidence evaluations, never a model-quality evaluation.

Role/pair fixtures test propagation of an existing validator's result. The real
Team Builder validator itself is exercised by the PostgreSQL integration suite.
No DB, HTTP transport, API key, solver or provider is used by this harness.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, TypeAdapter

from app.operations.checks import evaluate
from app.operations.schemas import (
    Activity,
    Actual,
    DogState,
    Eligibility,
    Entity,
    Frozen,
    Location,
    Snapshot,
    Status,
)

SELECTED_DATE = date(2026, 3, 29)
FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/operations-evals.json"


class ExpectedFact(Frozen):
    rule: str
    status: Status
    value_name: str
    value: int | str | bool | None


class EvalFixture(Frozen):
    name: str
    plan_exists: bool = False
    distances: tuple[int, ...] = ()
    actual_distances: tuple[int, ...] = ()
    actual_status: Literal["not_recorded", "not_run", "matches_plan"] = "not_recorded"
    eligibility_reasons: tuple[str, ...] = ()
    lineup_error: str | None = None
    missing_state: bool = False
    resident_count: int = Field(default=1, ge=1, le=4)
    dog_name: str = "Fixture working dog"
    expected: tuple[ExpectedFact, ...]


class EvalResult(Frozen):
    scenario: str
    status: Literal["PASS", "FAIL"]
    expected_rules: tuple[str, ...]
    matched_evidence_ids: tuple[str, ...]
    explanation: str = "Deterministic synthetic fixture; no LLM quality claim."


def load_fixtures(path: Path = FIXTURES) -> tuple[EvalFixture, ...]:
    return TypeAdapter(tuple[EvalFixture, ...]).validate_json(path.read_text())


def fixture_snapshot(fixture: EvalFixture) -> Snapshot:
    """Construct detached known entities; not a substitute for service capture."""
    dogs = tuple(
        DogState(
            id=UUID(int=index + 1),
            name=fixture.dog_name if index == 0 else f"Fixture dog {index + 1}",
            born=True,
            lifecycle="active",
            dog_class=None if fixture.missing_state else "standard",
            availability="available",
            capabilities=("lead", "team", "wheel"),
            housing_code=None if fixture.missing_state else "A1-01",
            housing_source="unhoused" if fixture.missing_state else "canonical",
            km_7d_before=10,
            km_14d_before=20,
            season_km_before=100,
            starts_14d_before=2,
            days_since_work_before=2,
            actual_km_on_date=sum(fixture.actual_distances),
            starts_on_date=len(fixture.actual_distances),
        )
        for index in range(fixture.resident_count)
    )
    selected = dogs[0].id
    activities = tuple(
        Activity(
            id=UUID(int=100 + index),
            sequence=index + 1,
            kind="training",
            distance_km=distance,
            participants=(selected,),
            eligibility=(
                Eligibility(dog_id=selected, reasons=fixture.eligibility_reasons),
            ),
            teams=(),
            lineup_error=fixture.lineup_error,
            actual_status=fixture.actual_status,
        )
        for index, distance in enumerate(fixture.distances)
    )
    actual = tuple(
        Actual(id=UUID(int=200 + index), distance_km=distance, participants=(selected,))
        for index, distance in enumerate(fixture.actual_distances)
    )
    locations = (
        Location(
            code="A1-01",
            nominal_capacity=2,
            residents=tuple(dog.id for dog in dogs)
            if not fixture.missing_state
            else (),
        ),
    )
    checks, evidence = evaluate(
        SELECTED_DATE,
        day=Entity(kind="day", id=SELECTED_DATE.isoformat()),
        activities=activities,
        dogs=dogs,
        actual=actual,
        locations=locations,
        plan_exists=fixture.plan_exists,
    )
    return Snapshot(
        id=UUID(int=999),
        captured_at=datetime(2026, 3, 31, tzinfo=UTC),
        selected_date=SELECTED_DATE,
        plan_exists=fixture.plan_exists,
        plan_revision=1 if fixture.plan_exists else None,
        activities=activities,
        dogs=dogs,
        actual=actual,
        locations=locations,
        checks=checks,
        evidence=evidence,
    )


def run_evaluations(path: Path = FIXTURES) -> tuple[EvalResult, ...]:
    results: list[EvalResult] = []
    for fixture in load_fixtures(path):
        snapshot = fixture_snapshot(fixture)
        evidence = {item.id: item for item in snapshot.evidence}
        matched: list[str] = []
        for expected in fixture.expected:
            found = [
                evidence[evidence_id]
                for check in snapshot.checks
                if check.rule == expected.rule and check.status == expected.status
                for evidence_id in check.evidence_ids
                if any(
                    value.name == expected.value_name and value.value == expected.value
                    for value in evidence[evidence_id].values
                )
            ]
            if found:
                matched.append(found[0].id)
        results.append(
            EvalResult(
                scenario=fixture.name,
                status="PASS" if len(matched) == len(fixture.expected) else "FAIL",
                expected_rules=tuple(expected.rule for expected in fixture.expected),
                matched_evidence_ids=tuple(matched),
            )
        )
    return tuple(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    results = run_evaluations(parser.parse_args().fixtures)
    print(json.dumps([item.model_dump(mode="json") for item in results], indent=2))
    return 0 if all(item.status == "PASS" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
