from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DemoDataset,
    Dog,
    DogArchive,
    DogAvailabilityPeriod,
    DogClassPeriod,
    DogLifecyclePeriod,
    DogRelationshipConstraint,
    DogRoleCapability,
    HousingAssignment,
    KennelLocation,
    Litter,
    WorkParticipation,
    WorkSession,
)


def _date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _work_session_row(work_session: WorkSession) -> dict[str, Any]:
    row: dict[str, Any] = {
        "reference": work_session.source_reference,
        "date": _date(work_session.work_date),
        "distance_km": work_session.distance_km,
        "activity_type": work_session.activity_type,
        "label": work_session.label,
        "note": work_session.note,
    }
    if work_session.start_time is not None:
        row["start_time"] = work_session.start_time.isoformat()
    return row


def _work_participation_row(
    participation: WorkParticipation,
    session_refs: dict[int, str],
    names: dict[int, str],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "session": session_refs[participation.session_id],
        "dog": names[participation.dog_id],
        "role": participation.assigned_role,
    }
    if participation.actual_team_sequence is not None:
        row.update(
            {
                "team": participation.actual_team_sequence,
                "pair_index": participation.pair_index,
                "side": participation.side,
                "position_order": participation.position_order,
            }
        )
    return row


def semantic_snapshot(session: Session) -> dict[str, Any]:
    """Return stable business data with database identities and timestamps removed."""
    dogs = session.scalars(select(Dog)).all()
    names = {dog.id: dog.name for dog in dogs}
    locations = session.scalars(select(KennelLocation)).all()
    location_codes = {location.id: location.code for location in locations}
    sessions = session.scalars(select(WorkSession)).all()
    session_refs = {
        work_session.id: work_session.source_reference for work_session in sessions
    }
    litters = session.scalars(select(Litter)).all()
    litter_codes = {litter.id: litter.code for litter in litters}
    datasets = session.scalars(select(DemoDataset)).all()

    return {
        "datasets": sorted(
            (
                {"version": dataset.version, "random_seed": dataset.random_seed}
                for dataset in datasets
            ),
            key=lambda row: row["version"],
        ),
        "dogs": sorted(
            (
                {
                    "public_id": str(dog.public_id),
                    "name": dog.name,
                    "birth_date": _date(dog.birth_date),
                    "sex": dog.sex,
                    "neutered_on": _date(dog.neutered_on),
                    "litter": litter_codes[dog.litter_id] if dog.litter_id else None,
                    # Preserve the v1 checksum shape while excluding independently
                    # versioned media activation from domain semantics.
                    "photo_key": None,
                    "notes": dog.notes,
                }
                for dog in dogs
            ),
            key=lambda row: row["name"],
        ),
        "litters": sorted(
            (
                {
                    "code": litter.code,
                    "birth_date": _date(litter.birth_date),
                    "mother": names[litter.mother_id] if litter.mother_id else None,
                    "father": names[litter.father_id] if litter.father_id else None,
                    "notes": litter.notes,
                }
                for litter in litters
            ),
            key=lambda row: row["code"],
        ),
        "class_periods": sorted(
            (
                {
                    "dog": names[period.dog_id],
                    "class": period.dog_class,
                    "from": _date(period.valid_from),
                    "to": _date(period.valid_to),
                }
                for period in session.scalars(select(DogClassPeriod))
            ),
            key=lambda row: (row["dog"], row["from"] or ""),
        ),
        "lifecycle_periods": sorted(
            (
                {
                    "dog": names[period.dog_id],
                    "state": period.lifecycle_state,
                    "from": _date(period.valid_from),
                    "to": _date(period.valid_to),
                }
                for period in session.scalars(select(DogLifecyclePeriod))
            ),
            key=lambda row: (row["dog"], row["from"] or ""),
        ),
        "availability_periods": sorted(
            (
                {
                    "dog": names[period.dog_id],
                    "state": period.availability_state,
                    "from": _date(period.valid_from),
                    "to": _date(period.valid_to),
                    "note": period.note,
                }
                for period in session.scalars(select(DogAvailabilityPeriod))
            ),
            key=lambda row: (row["dog"], row["from"] or ""),
        ),
        "archives": sorted(
            (
                {
                    "dog": names[archive.dog_id],
                    "date": _date(archive.archive_date),
                    "reason": archive.reason,
                    "note": archive.note,
                }
                for archive in session.scalars(select(DogArchive))
            ),
            key=lambda row: row["dog"],
        ),
        "roles": sorted(
            (
                {"dog": names[role.dog_id], "role": role.role}
                for role in session.scalars(select(DogRoleCapability))
            ),
            key=lambda row: (row["dog"], row["role"]),
        ),
        "locations": sorted(
            (
                {
                    "code": location.code,
                    "display_name": location.display_name,
                    "type": location.location_type,
                    "zone": location.zone,
                    "row": location.row_label,
                    "position": location.position,
                    "capacity": location.capacity,
                    "active": location.is_active,
                }
                for location in locations
            ),
            key=lambda row: row["code"],
        ),
        "housing": sorted(
            (
                {
                    "dog": names[assignment.dog_id],
                    "location": location_codes[assignment.location_id],
                    "from": _date(assignment.valid_from),
                    "to": _date(assignment.valid_to),
                    "note": assignment.note,
                }
                for assignment in session.scalars(select(HousingAssignment))
            ),
            key=lambda row: (row["dog"], row["from"] or ""),
        ),
        "relationships": sorted(
            (
                {
                    "dog_a": names[relation.dog_a_id],
                    "dog_b": names[relation.dog_b_id],
                    "kind": relation.relationship_kind,
                    "note": relation.note,
                }
                for relation in session.scalars(select(DogRelationshipConstraint))
            ),
            key=lambda row: (row["kind"], row["dog_a"], row["dog_b"]),
        ),
        "work_sessions": sorted(
            (_work_session_row(work_session) for work_session in sessions),
            key=lambda row: row["reference"],
        ),
        "work_participations": sorted(
            (
                _work_participation_row(participation, session_refs, names)
                for participation in session.scalars(select(WorkParticipation))
            ),
            key=lambda row: (row["session"], row["dog"]),
        ),
    }


def semantic_checksum(session: Session) -> str:
    payload = json.dumps(
        semantic_snapshot(session),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
