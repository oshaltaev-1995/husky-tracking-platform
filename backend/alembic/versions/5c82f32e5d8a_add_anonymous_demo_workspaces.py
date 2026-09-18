"""add anonymous demo workspaces

Revision ID: 5c82f32e5d8a
Revises: c4e87a1b92f0
Create Date: 2026-09-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5c82f32e5d8a"
down_revision: str | None = "c4e87a1b92f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("public_id", name="uq_demo_workspaces_public_id"),
        sa.UniqueConstraint("token_hash", name="uq_demo_workspaces_token_hash"),
    )
    op.create_index("ix_demo_workspaces_expires_at", "demo_workspaces", ["expires_at"])
    op.create_table(
        "demo_workspace_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["demo_workspaces.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("workspace_id", "work_date", name="uq_workspace_day"),
    )
    op.create_index(
        "ix_demo_workspace_days_workspace_id", "demo_workspace_days", ["workspace_id"]
    )
    op.create_index(
        "ix_demo_workspace_days_work_date", "demo_workspace_days", ["work_date"]
    )

    op.add_column(
        "daily_plans", sa.Column("demo_workspace_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_daily_plans_demo_workspace_id",
        "daily_plans",
        "demo_workspaces",
        ["demo_workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_daily_plans_demo_workspace_id", "daily_plans", ["demo_workspace_id"]
    )
    op.drop_index("ix_daily_plans_plan_date", table_name="daily_plans")
    op.drop_constraint("daily_plans_public_id_key", "daily_plans", type_="unique")
    op.create_index("ix_daily_plans_plan_date", "daily_plans", ["plan_date"])
    op.create_index(
        "uq_daily_plans_baseline_date",
        "daily_plans",
        ["plan_date"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NULL"),
    )
    op.create_index(
        "uq_daily_plans_workspace_date",
        "daily_plans",
        ["demo_workspace_id", "plan_date"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NOT NULL"),
    )
    op.create_index(
        "uq_daily_plans_baseline_public_id",
        "daily_plans",
        ["public_id"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NULL"),
    )
    op.create_index(
        "uq_daily_plans_workspace_public_id",
        "daily_plans",
        ["demo_workspace_id", "public_id"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NOT NULL"),
    )

    op.drop_constraint(
        "planned_activities_public_id_key", "planned_activities", type_="unique"
    )
    op.create_unique_constraint(
        "uq_planned_activity_plan_public_id",
        "planned_activities",
        ["daily_plan_id", "public_id"],
    )

    op.add_column(
        "work_sessions", sa.Column("demo_workspace_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_work_sessions_demo_workspace_id",
        "work_sessions",
        "demo_workspaces",
        ["demo_workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_work_sessions_demo_workspace_id", "work_sessions", ["demo_workspace_id"]
    )
    op.create_index(
        "ix_work_sessions_workspace_date",
        "work_sessions",
        ["demo_workspace_id", "work_date"],
    )
    op.drop_constraint("uq_work_sessions_public_id", "work_sessions", type_="unique")
    op.drop_constraint(
        "work_sessions_source_reference_key", "work_sessions", type_="unique"
    )
    op.create_index(
        "uq_work_sessions_baseline_public_id",
        "work_sessions",
        ["public_id"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NULL"),
    )
    op.create_index(
        "uq_work_sessions_workspace_public_id",
        "work_sessions",
        ["demo_workspace_id", "public_id"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NOT NULL"),
    )
    op.create_index(
        "uq_work_sessions_baseline_source",
        "work_sessions",
        ["source_reference"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NULL"),
    )
    op.create_index(
        "uq_work_sessions_workspace_source",
        "work_sessions",
        ["demo_workspace_id", "source_reference"],
        unique=True,
        postgresql_where=sa.text("demo_workspace_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_work_sessions_workspace_source", table_name="work_sessions")
    op.drop_index("uq_work_sessions_baseline_source", table_name="work_sessions")
    op.drop_index("uq_work_sessions_workspace_public_id", table_name="work_sessions")
    op.drop_index("uq_work_sessions_baseline_public_id", table_name="work_sessions")
    op.create_unique_constraint(
        "work_sessions_source_reference_key", "work_sessions", ["source_reference"]
    )
    op.create_unique_constraint(
        "uq_work_sessions_public_id", "work_sessions", ["public_id"]
    )
    op.drop_index("ix_work_sessions_workspace_date", table_name="work_sessions")
    op.drop_index("ix_work_sessions_demo_workspace_id", table_name="work_sessions")
    op.drop_constraint(
        "fk_work_sessions_demo_workspace_id", "work_sessions", type_="foreignkey"
    )
    op.drop_column("work_sessions", "demo_workspace_id")

    op.drop_constraint(
        "uq_planned_activity_plan_public_id", "planned_activities", type_="unique"
    )
    op.create_unique_constraint(
        "planned_activities_public_id_key", "planned_activities", ["public_id"]
    )

    op.drop_index("uq_daily_plans_workspace_public_id", table_name="daily_plans")
    op.drop_index("uq_daily_plans_baseline_public_id", table_name="daily_plans")
    op.drop_index("uq_daily_plans_workspace_date", table_name="daily_plans")
    op.drop_index("uq_daily_plans_baseline_date", table_name="daily_plans")
    op.drop_index("ix_daily_plans_plan_date", table_name="daily_plans")
    op.create_index(
        "ix_daily_plans_plan_date", "daily_plans", ["plan_date"], unique=True
    )
    op.create_unique_constraint(
        "daily_plans_public_id_key", "daily_plans", ["public_id"]
    )
    op.drop_index("ix_daily_plans_demo_workspace_id", table_name="daily_plans")
    op.drop_constraint(
        "fk_daily_plans_demo_workspace_id", "daily_plans", type_="foreignkey"
    )
    op.drop_column("daily_plans", "demo_workspace_id")
    op.drop_index("ix_demo_workspace_days_work_date", table_name="demo_workspace_days")
    op.drop_index(
        "ix_demo_workspace_days_workspace_id", table_name="demo_workspace_days"
    )
    op.drop_table("demo_workspace_days")
    op.drop_index("ix_demo_workspaces_expires_at", table_name="demo_workspaces")
    op.drop_table("demo_workspaces")
