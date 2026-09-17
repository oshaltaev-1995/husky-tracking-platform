"""add daily planning workspace

Revision ID: 83ee450cd525
Revises: 0cc49c993626
Create Date: 2026-09-17 16:58:25.430280
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "83ee450cd525"
down_revision: str | None = "0cc49c993626"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("revision > 0", name="ck_daily_plans_positive_revision"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(
        "ix_daily_plans_plan_date", "daily_plans", ["plan_date"], unique=True
    )

    op.create_table(
        "planned_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_plan_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("distance_km", sa.SmallInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "activity_type IN "
            "('training', 'open_space_walk', 'individual_exercise', 'rest')",
            name="ck_planned_activities_type",
        ),
        sa.CheckConstraint(
            "(activity_type = 'training' AND distance_km IN (5, 10)) OR "
            "(activity_type <> 'training' AND distance_km IS NULL)",
            name="ck_planned_activities_distance",
        ),
        sa.CheckConstraint("sequence > 0", name="ck_planned_activities_sequence"),
        sa.CheckConstraint(
            "char_length(btrim(title)) > 0",
            name="ck_planned_activities_title",
        ),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"], ["daily_plans.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "daily_plan_id",
            "sequence",
            name="uq_planned_activity_sequence",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index(
        "ix_planned_activities_activity_type",
        "planned_activities",
        ["activity_type"],
    )
    op.create_index(
        "ix_planned_activities_daily_plan_id",
        "planned_activities",
        ["daily_plan_id"],
    )

    op.create_table(
        "planned_activity_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("planned_activity_id", sa.Integer(), nullable=False),
        sa.Column("dog_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["planned_activity_id"], ["planned_activities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "planned_activity_id",
            "dog_id",
            name="uq_planned_activity_participant",
        ),
    )
    op.create_index(
        "ix_planned_activity_participants_planned_activity_id",
        "planned_activity_participants",
        ["planned_activity_id"],
    )
    op.create_index(
        "ix_planned_activity_participants_dog_id",
        "planned_activity_participants",
        ["dog_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_planned_activity_participants_dog_id",
        table_name="planned_activity_participants",
    )
    op.drop_index(
        "ix_planned_activity_participants_planned_activity_id",
        table_name="planned_activity_participants",
    )
    op.drop_table("planned_activity_participants")
    op.drop_index(
        "ix_planned_activities_daily_plan_id", table_name="planned_activities"
    )
    op.drop_index(
        "ix_planned_activities_activity_type", table_name="planned_activities"
    )
    op.drop_table("planned_activities")
    op.drop_index("ix_daily_plans_plan_date", table_name="daily_plans")
    op.drop_table("daily_plans")
