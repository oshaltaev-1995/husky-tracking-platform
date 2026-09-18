from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.catalog import (
    DEMO_DATASET_VERSION,
    EXPECTED_SEMANTIC_CHECKSUM,
    FORBIDDEN_STREAMLIT_NAMES,
)
from app.demo.semantic import semantic_checksum
from app.demo.service import reset_demo_world
from app.demo.validation import DemoValidationError, validate_demo_world
from app.domain.workload import MAX_DAILY_DOG_DISTANCE_KM
from app.main import app
from app.models import (
    DailyPlan,
    Dog,
    DogClassPeriod,
    Litter,
    PlannedActivity,
    PlannedActivityParticipant,
    WorkParticipation,
    WorkSession,
)


def test_reset_clears_mutable_plans_without_changing_core_checksum() -> None:
    clock = DemoClock.from_settings(get_settings())
    with SessionLocal.begin() as session:
        reset_demo_world(session, clock, require_enabled=False)
    with SessionLocal.begin() as session:
        atlas = session.scalar(select(Dog).where(Dog.name == "Atlas"))
        assert atlas is not None
        plan = DailyPlan(plan_date=date(2026, 3, 31), revision=1)
        session.add(plan)
        session.flush()
        activity = PlannedActivity(
            daily_plan_id=plan.id,
            activity_type="training",
            sequence=1,
            start_time=None,
            title="Reset fixture",
            distance_km=5,
        )
        session.add(activity)
        session.flush()
        session.add(
            PlannedActivityParticipant(planned_activity_id=activity.id, dog_id=atlas.id)
        )

    with SessionLocal.begin() as session:
        checksum = reset_demo_world(session, clock, require_enabled=False)
        assert session.scalar(select(func.count()).select_from(DailyPlan)) == 0

    assert checksum == EXPECTED_SEMANTIC_CHECKSUM


def test_two_postgres_resets_have_identical_semantic_checksum() -> None:
    clock = DemoClock.from_settings(get_settings())

    with SessionLocal.begin() as session:
        checksum_a = reset_demo_world(session, clock, require_enabled=False)
        report_a = validate_demo_world(session, clock)
    with SessionLocal.begin() as session:
        checksum_b = reset_demo_world(session, clock, require_enabled=False)
        report_b = validate_demo_world(session, clock)

    assert checksum_a == checksum_b
    assert checksum_a == EXPECTED_SEMANTIC_CHECKSUM
    assert report_a.checksum == report_b.checksum == checksum_a
    assert report_b.dataset_version == DEMO_DATASET_VERSION
    assert (report_b.dog_count, report_b.active_count, report_b.archived_count) == (
        60,
        50,
        10,
    )
    assert report_b.class_counts == {
        "junior": 6,
        "puppy": 10,
        "standard": 26,
        "training": 8,
    }
    assert report_b.archive_reason_counts == {
        "deceased": 3,
        "euthanized": 3,
        "rehomed_to_guide": 4,
    }
    assert report_b.adult_enclosure_count == 20
    assert report_b.puppy_area_count == 2
    assert report_b.session_count == 140
    assert report_b.participation_count == 1120
    assert report_b.distance_session_counts == {5: 70, 10: 70}
    assert report_b.max_daily_dog_distance_km == 10
    assert report_b.max_daily_dog_distance_km <= MAX_DAILY_DOG_DISTANCE_KM

    with SessionLocal() as session:
        seeded_dogs = session.scalars(select(Dog).order_by(Dog.name)).all()
        assert len(seeded_dogs) == 60
        assert all(dog.photo_key == f"{dog.public_id}.webp" for dog in seeded_dogs)

    response = TestClient(app).get("/api/v1/demo-dataset")
    assert response.status_code == 200
    assert response.json() == {
        "dataset_version": DEMO_DATASET_VERSION,
        "reference_date": "2026-03-31",
        "active_dogs": 50,
        "archived_dogs": 10,
        "semantic_checksum": EXPECTED_SEMANTIC_CHECKSUM,
    }


def test_media_activation_is_outside_the_domain_semantic_checksum() -> None:
    with SessionLocal() as session:
        aurora = session.scalar(select(Dog).where(Dog.name == "Aurora"))
        assert aurora is not None
        checksum_before = semantic_checksum(session)
        aurora.photo_key = None
        session.flush()
        assert semantic_checksum(session) == checksum_before
        session.rollback()


def test_seeded_postgres_population_excludes_owner_forbidden_names() -> None:
    with SessionLocal() as session:
        seeded_names = set(session.scalars(select(Dog.name)))

    assert seeded_names.isdisjoint(FORBIDDEN_STREAMLIT_NAMES)


def test_semantic_validator_rejects_impossible_self_parent() -> None:
    clock = DemoClock.from_settings(get_settings())
    with SessionLocal() as session, session.begin():
        litter = session.scalar(select(Litter).where(Litter.code == "S"))
        sage = session.scalar(select(Dog).where(Dog.name == "Sage"))
        assert litter is not None and sage is not None
        original_mother_id = litter.mother_id
        litter.mother_id = sage.id
        session.flush()

        with pytest.raises(DemoValidationError, match="own parent|too young"):
            validate_demo_world(session, clock)

        litter.mother_id = original_mother_id
        session.flush()


def test_semantic_validator_rejects_pedigree_cycle() -> None:
    clock = DemoClock.from_settings(get_settings())
    with SessionLocal() as session, session.begin():
        litter = session.scalar(select(Litter).where(Litter.code == "C"))
        nova = session.scalar(select(Dog).where(Dog.name == "Nova"))
        assert litter is not None and nova is not None
        original_mother_id = litter.mother_id
        litter.mother_id = nova.id
        session.flush()

        with pytest.raises(DemoValidationError, match="pedigree cycle"):
            validate_demo_world(session, clock)

        litter.mother_id = original_mother_id
        session.flush()


def test_semantic_validator_rejects_litter_date_and_prefix_mismatch() -> None:
    clock = DemoClock.from_settings(get_settings())
    with SessionLocal() as session, session.begin():
        cedar = session.scalar(select(Dog).where(Dog.name == "Cedar"))
        assert cedar is not None
        original_name = cedar.name
        original_birth_date = cedar.birth_date
        cedar.name = "Zedar"
        cedar.birth_date = date(2018, 6, 16)
        session.flush()

        with pytest.raises(
            DemoValidationError, match="birth date differs|does not begin"
        ):
            validate_demo_world(session, clock)

        cedar.name = original_name
        cedar.birth_date = original_birth_date
        session.flush()


def test_semantic_validator_rejects_dog_day_above_30_km() -> None:
    clock = DemoClock.from_settings(get_settings())
    with SessionLocal() as session, session.begin():
        atlas = session.scalar(select(Dog).where(Dog.name == "Atlas"))
        assert atlas is not None
        existing = session.scalar(
            select(WorkParticipation)
            .join(WorkSession)
            .where(
                WorkParticipation.dog_id == atlas.id,
                WorkSession.work_date == date(2025, 12, 1),
            )
        )
        assert existing is not None

        nested = session.begin_nested()
        for sequence, distance in enumerate((10, 10, 5), start=1):
            work_session = WorkSession(
                source_reference=f"test:daily-limit:{sequence}",
                work_date=date(2025, 12, 1),
                distance_km=distance,
                activity_type="sled_training",
                label="Daily-limit validation fixture",
            )
            session.add(work_session)
            session.flush()
            session.add(
                WorkParticipation(
                    session_id=work_session.id,
                    dog_id=atlas.id,
                    assigned_role=existing.assigned_role,
                )
            )
        session.flush()

        with pytest.raises(DemoValidationError, match="exceeds 30 km"):
            validate_demo_world(session, clock)
        nested.rollback()


def test_database_rejects_same_mother_and_father() -> None:
    with SessionLocal() as session, session.begin():
        litter = session.scalar(select(Litter).where(Litter.code == "D"))
        assert litter is not None
        nested = session.begin_nested()
        litter.father_id = litter.mother_id
        with pytest.raises(IntegrityError):
            session.flush()
        nested.rollback()


def test_postgres_exclusion_constraint_rejects_overlapping_class_periods() -> None:
    with SessionLocal() as session, session.begin():
        aurora = session.scalar(select(Dog).where(Dog.name == "Aurora"))
        assert aurora is not None
        nested = session.begin_nested()
        session.add(
            DogClassPeriod(
                dog_id=aurora.id,
                dog_class="standard",
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 2, 1),
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        nested.rollback()
