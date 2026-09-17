from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import DATERANGE, ExcludeConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_VALID_RANGE_SQL = "daterange(valid_from, COALESCE(valid_to, '9999-12-31'::date), '[)')"


class DemoDataset(Base):
    __tablename__ = "demo_datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(80), unique=True)
    random_seed: Mapped[int]
    semantic_checksum: Mapped[str | None] = mapped_column(String(64))
    seeded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Dog(Base):
    __tablename__ = "dogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    birth_date: Mapped[date] = mapped_column(Date, index=True)
    sex: Mapped[str] = mapped_column(String(16))
    is_neutered: Mapped[bool] = mapped_column(Boolean, default=False)
    neutered_on: Mapped[date | None] = mapped_column(Date)
    litter_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "litters.id", ondelete="RESTRICT", use_alter=True, name="fk_dogs_litter_id"
        )
    )
    photo_key: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("sex IN ('female', 'male')", name="ck_dogs_sex"),
        CheckConstraint(
            "neutered_on IS NULL OR neutered_on >= birth_date",
            name="ck_dogs_neutered_after_birth",
        ),
        Index("uq_dogs_name_lower", func.lower(name), unique=True),
    )

    litter: Mapped[Litter | None] = relationship(
        back_populates="members", foreign_keys=[litter_id]
    )
    class_periods: Mapped[list[DogClassPeriod]] = relationship(back_populates="dog")
    lifecycle_periods: Mapped[list[DogLifecyclePeriod]] = relationship(
        back_populates="dog"
    )
    availability_periods: Mapped[list[DogAvailabilityPeriod]] = relationship(
        back_populates="dog"
    )
    archive: Mapped[DogArchive | None] = relationship(
        back_populates="dog", uselist=False
    )
    role_capabilities: Mapped[list[DogRoleCapability]] = relationship(
        back_populates="dog"
    )
    housing_assignments: Mapped[list[HousingAssignment]] = relationship(
        back_populates="dog"
    )


class Litter(Base):
    __tablename__ = "litters"
    __table_args__ = (
        CheckConstraint("char_length(code) = 1", name="ck_litters_single_letter_code"),
        CheckConstraint(
            "mother_id IS NULL OR father_id IS NULL OR mother_id <> father_id",
            name="ck_litters_distinct_parents",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(1), unique=True)
    birth_date: Mapped[date] = mapped_column(Date, index=True)
    mother_id: Mapped[int | None] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    father_id: Mapped[int | None] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    mother: Mapped[Dog | None] = relationship(foreign_keys=[mother_id])
    father: Mapped[Dog | None] = relationship(foreign_keys=[father_id])
    members: Mapped[list[Dog]] = relationship(
        back_populates="litter", foreign_keys=[Dog.litter_id]
    )


class DogClassPeriod(Base):
    __tablename__ = "dog_class_periods"
    __table_args__ = (
        CheckConstraint(
            "dog_class IN ('puppy', 'junior', 'training', 'standard')",
            name="ck_dog_class_periods_class",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_class_valid_range"
        ),
        ExcludeConstraint(
            ("dog_id", "="),
            ("valid_range", "&&"),
            using="gist",
            name="excl_dog_class_periods_overlap",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    dog_class: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    valid_range: Mapped[Any] = mapped_column(
        DATERANGE, Computed(_VALID_RANGE_SQL, persisted=True), nullable=False
    )

    dog: Mapped[Dog] = relationship(back_populates="class_periods")


class DogLifecyclePeriod(Base):
    __tablename__ = "dog_lifecycle_periods"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_state IN ('active', 'archived')",
            name="ck_dog_lifecycle_periods_state",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_lifecycle_valid_range"
        ),
        ExcludeConstraint(
            ("dog_id", "="),
            ("valid_range", "&&"),
            using="gist",
            name="excl_dog_lifecycle_periods_overlap",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    lifecycle_state: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    valid_range: Mapped[Any] = mapped_column(
        DATERANGE, Computed(_VALID_RANGE_SQL, persisted=True), nullable=False
    )

    dog: Mapped[Dog] = relationship(back_populates="lifecycle_periods")


class DogAvailabilityPeriod(Base):
    __tablename__ = "dog_availability_periods"
    __table_args__ = (
        CheckConstraint(
            "availability_state IN "
            "('available', 'injured', 'rest', 'restricted', 'retired')",
            name="ck_dog_availability_periods_state",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_availability_valid_range",
        ),
        ExcludeConstraint(
            ("dog_id", "="),
            ("valid_range", "&&"),
            using="gist",
            name="excl_dog_availability_periods_overlap",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    availability_state: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    valid_range: Mapped[Any] = mapped_column(
        DATERANGE, Computed(_VALID_RANGE_SQL, persisted=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(255))

    dog: Mapped[Dog] = relationship(back_populates="availability_periods")


class DogArchive(Base):
    __tablename__ = "dog_archives"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('euthanized', 'deceased', 'rehomed_to_guide')",
            name="ck_dog_archives_reason",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), unique=True, index=True
    )
    archive_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(String(255))

    dog: Mapped[Dog] = relationship(back_populates="archive")


class DogRoleCapability(Base):
    __tablename__ = "dog_role_capabilities"
    __table_args__ = (
        CheckConstraint(
            "role IN ('lead', 'team', 'wheel')", name="ck_role_capabilities_role"
        ),
        UniqueConstraint("dog_id", "role", name="uq_dog_role_capability"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))

    dog: Mapped[Dog] = relationship(back_populates="role_capabilities")


class KennelLocation(Base):
    __tablename__ = "kennel_locations"
    __table_args__ = (
        CheckConstraint(
            "location_type IN ('adult_enclosure', 'puppy_area')",
            name="ck_kennel_locations_type",
        ),
        CheckConstraint("capacity > 0", name="ck_kennel_locations_positive_capacity"),
        UniqueConstraint(
            "zone", "row_label", "position", name="uq_location_map_position"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    location_type: Mapped[str] = mapped_column(String(30), index=True)
    zone: Mapped[str] = mapped_column(String(30))
    row_label: Mapped[str] = mapped_column(String(30))
    position: Mapped[int]
    capacity: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    housing_assignments: Mapped[list[HousingAssignment]] = relationship(
        back_populates="location"
    )


class HousingAssignment(Base):
    __tablename__ = "housing_assignments"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_housing_valid_range"
        ),
        ExcludeConstraint(
            ("dog_id", "="),
            ("valid_range", "&&"),
            using="gist",
            name="excl_housing_assignments_dog_overlap",
        ),
        Index(
            "ix_housing_assignments_location_dates",
            "location_id",
            "valid_from",
            "valid_to",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("kennel_locations.id", ondelete="RESTRICT"), index=True
    )
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    valid_range: Mapped[Any] = mapped_column(
        DATERANGE, Computed(_VALID_RANGE_SQL, persisted=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(255))

    dog: Mapped[Dog] = relationship(back_populates="housing_assignments")
    location: Mapped[KennelLocation] = relationship(
        back_populates="housing_assignments"
    )


class DogRelationshipConstraint(Base):
    __tablename__ = "dog_relationship_constraints"
    __table_args__ = (
        CheckConstraint(
            "dog_a_id < dog_b_id", name="ck_relationship_canonical_pair_order"
        ),
        CheckConstraint(
            "relationship_kind IN ('preferred_pair', 'hard_conflict')",
            name="ck_relationship_kind",
        ),
        UniqueConstraint(
            "dog_a_id",
            "dog_b_id",
            "relationship_kind",
            name="uq_relationship_pair_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dog_a_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    dog_b_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    relationship_kind: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(String(255))

    dog_a: Mapped[Dog] = relationship(foreign_keys=[dog_a_id])
    dog_b: Mapped[Dog] = relationship(foreign_keys=[dog_b_id])


class WorkSession(Base):
    __tablename__ = "work_sessions"
    __table_args__ = (
        CheckConstraint(
            "distance_km IN (5, 10)", name="ck_work_sessions_canonical_distance"
        ),
        CheckConstraint(
            "activity_type = 'sled_training'", name="ck_work_sessions_activity_type"
        ),
        Index("ix_work_sessions_work_date_distance", "work_date", "distance_km"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_reference: Mapped[str] = mapped_column(String(80), unique=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    distance_km: Mapped[int] = mapped_column(SmallInteger)
    activity_type: Mapped[str] = mapped_column(String(30), default="sled_training")
    label: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(255))

    participations: Mapped[list[WorkParticipation]] = relationship(
        back_populates="session"
    )


class WorkParticipation(Base):
    __tablename__ = "work_participations"
    __table_args__ = (
        CheckConstraint(
            "assigned_role IS NULL OR assigned_role IN ('lead', 'team', 'wheel')",
            name="ck_work_participations_role",
        ),
        UniqueConstraint("session_id", "dog_id", name="uq_work_participation_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="RESTRICT"), index=True
    )
    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="RESTRICT"), index=True
    )
    assigned_role: Mapped[str | None] = mapped_column(String(20))

    session: Mapped[WorkSession] = relationship(back_populates="participations")
    dog: Mapped[Dog] = relationship()
