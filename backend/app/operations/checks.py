from __future__ import annotations

from datetime import date

from app.domain.workload import WorkloadRuleViolation, validate_daily_dog_distances
from app.operations.schemas import (
    Activity,
    Actual,
    Check,
    DogState,
    Entity,
    Evidence,
    Location,
    Status,
    Value,
)


def evaluate(
    on_date: date,
    *,
    day: Entity,
    activities: tuple[Activity, ...],
    dogs: tuple[DogState, ...],
    actual: tuple[Actual, ...],
    locations: tuple[Location, ...],
    plan_exists: bool,
) -> tuple[tuple[Check, ...], tuple[Evidence, ...]]:
    """Reuse canonical arithmetic and the services' eligibility/lineup facts."""
    checks: list[Check] = []
    evidence: list[Evidence] = []

    def add(
        code: str,
        status: Status,
        text: str,
        entities: tuple[Entity, ...],
        values: tuple[Value, ...],
    ) -> None:
        evidence_id = f"e-{len(evidence) + 1:03}"
        evidence.append(
            Evidence(
                id=evidence_id, selected_date=on_date, entities=entities, values=values
            )
        )
        checks.append(
            Check(
                rule=code,
                status=status,
                explanation=text,
                selected_date=on_date,
                entities=entities,
                evidence_ids=(evidence_id,),
            )
        )

    def count(name: str, value: int) -> Value:
        return Value(name=name, value=value, unit="count")

    add(
        "PLAN_PRESENCE",
        "pass" if plan_exists else "attention",
        "Saved plan present."
        if plan_exists
        else "No saved plan; no completion is inferred.",
        (day,),
        (count("activities", len(activities)),),
    )
    for activity in activities:
        ref = Entity(kind="activity", id=str(activity.id))
        distance_valid = True
        if activity.kind == "training":
            try:
                validate_daily_dog_distances([activity.distance_km or 0])
            except WorkloadRuleViolation:
                distance_valid = False
        elif activity.distance_km is not None:
            distance_valid = False
        add(
            "ACTIVITY_DISTANCE",
            "pass" if distance_valid else "violation",
            "Uses the existing activity distance contract.",
            (ref,),
            (Value(name="distance", value=activity.distance_km, unit="km"),),
        )
        invalid = tuple(item for item in activity.eligibility if item.reasons)
        add(
            "PARTICIPANT_ELIGIBILITY",
            "violation" if invalid else "pass",
            "Date-effective eligibility from Daily Plan; "
            "no alternative class/status policy.",
            (ref, *(Entity(kind="dog", id=str(item.dog_id)) for item in invalid)),
            (
                count("ineligible_participants", len(invalid)),
                count("selected_participants", len(activity.participants)),
            ),
        )
        if activity.kind == "training":
            add(
                "SAVED_LINEUP",
                "violation"
                if activity.lineup_error
                else "pass"
                if activity.teams
                else "attention",
                "Saved lineup checked by existing Team Builder validator."
                if activity.teams
                else "No saved teams; selected pool is not an arranged harness.",
                (ref,),
                (
                    count("saved_teams", len(activity.teams)),
                    Value(
                        name="validator_code", value=activity.lineup_error, unit="state"
                    ),
                ),
            )
        add(
            "ACTUAL_RECORDING",
            "attention" if activity.actual_status == "not_recorded" else "pass",
            "Planned work is not evidence of completed work.",
            (ref,),
            (
                Value(
                    name="recording_status", value=activity.actual_status, unit="state"
                ),
            ),
        )
    for dog in dogs:
        ref = Entity(kind="dog", id=str(dog.id))
        add(
            "DOG_STATE",
            "pass"
            if not dog.born or dog.lifecycle and dog.dog_class and dog.availability
            else "unverified",
            "Dated lifecycle, class and availability are distinct; "
            "capabilities are explicit stored roles.",
            (ref,),
            (
                Value(name="born", value=dog.born, unit="state"),
                Value(name="lifecycle", value=dog.lifecycle, unit="state"),
                Value(name="class", value=dog.dog_class, unit="state"),
                Value(name="availability", value=dog.availability, unit="state"),
                Value(name="roles", value=",".join(dog.capabilities), unit="state"),
                Value(name="housing", value=dog.housing_code, unit="state"),
                Value(name="housing_source", value=dog.housing_source, unit="state"),
            ),
        )
        add(
            "WORKLOAD_BEFORE",
            "pass",
            "Actual work strictly before the selected date; "
            "today's actual is separate.",
            (ref,),
            (
                Value(name="km_7d_before", value=dog.km_7d_before, unit="km"),
                Value(name="km_14d_before", value=dog.km_14d_before, unit="km"),
                Value(name="season_km_before", value=dog.season_km_before, unit="km"),
                count("starts_14d_before", dog.starts_14d_before),
                Value(
                    name="days_since_work_before",
                    value=dog.days_since_work_before,
                    unit="days",
                ),
                Value(name="actual_km_on_date", value=dog.actual_km_on_date, unit="km"),
                count("starts_on_date", dog.starts_on_date),
            ),
        )
        for code, distances in (
            (
                "PLANNED_DAILY_KM",
                [
                    item.distance_km or 0
                    for item in activities
                    if item.kind == "training" and dog.id in item.participants
                ],
            ),
            (
                "ACTUAL_DAILY_KM",
                [item.distance_km for item in actual if dog.id in item.participants],
            ),
        ):
            if not distances:
                continue
            try:
                total = validate_daily_dog_distances(distances)
                status: Status = "pass"
            except WorkloadRuleViolation:
                total, status = sum(distances), "violation"
            add(
                code,
                status,
                "Planned and actual totals are independent; "
                "canonical daily limit applies separately.",
                (ref,),
                (
                    Value(name="total", value=total, unit="km"),
                    count("starts_or_activities", len(distances)),
                ),
            )
        if (
            dog.born
            and dog.lifecycle == "active"
            and (
                dog.dog_class is None
                or dog.availability is None
                or dog.housing_code is None
            )
        ):
            add(
                "DATED_STATE_MISSING",
                "unverified",
                "Dated domain information is missing; do not infer a replacement.",
                (ref,),
                (
                    Value(name="class", value=dog.dog_class, unit="state"),
                    Value(name="availability", value=dog.availability, unit="state"),
                    Value(name="housing", value=dog.housing_code, unit="state"),
                ),
            )
    for location in locations:
        add(
            "HOUSING_INFORMATION",
            "pass",
            "Nominal capacity is informational, not a move or training limit.",
            (Entity(kind="location", id=location.code),),
            (
                count("residents", len(location.residents)),
                count("nominal_capacity", location.nominal_capacity),
            ),
        )
    add(
        "ACTUAL_LEDGER",
        "pass",
        "Actual session participations only; planned and not-run work excluded.",
        (day,),
        (
            count("sessions", len(actual)),
            count("dog_starts", sum(len(item.participants) for item in actual)),
            Value(
                name="dog_km",
                value=sum(item.distance_km * len(item.participants) for item in actual),
                unit="km",
            ),
        ),
    )
    return tuple(checks), tuple(evidence)
