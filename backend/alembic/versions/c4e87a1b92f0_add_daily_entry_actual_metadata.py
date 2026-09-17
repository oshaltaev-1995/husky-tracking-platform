"""add daily entry actual metadata

Revision ID: c4e87a1b92f0
Revises: 9fa6b3d1c204
Create Date: 2026-09-17 20:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4e87a1b92f0"
down_revision: str | None = "9fa6b3d1c204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "planned_activities",
        sa.Column(
            "actual_not_run",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.add_column(
        "work_sessions",
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("UPDATE work_sessions SET public_id = gen_random_uuid()")
    op.alter_column("work_sessions", "public_id", nullable=False)
    op.add_column(
        "work_sessions",
        sa.Column("planned_activity_id", sa.Integer(), nullable=True),
    )
    op.add_column("work_sessions", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column(
        "work_sessions",
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "work_sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "work_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_work_sessions_positive_revision", "work_sessions", "revision > 0"
    )
    op.create_unique_constraint(
        "uq_work_sessions_public_id", "work_sessions", ["public_id"]
    )
    op.create_unique_constraint(
        "uq_work_sessions_planned_activity_id",
        "work_sessions",
        ["planned_activity_id"],
    )
    op.create_foreign_key(
        "fk_work_sessions_planned_activity_id",
        "work_sessions",
        "planned_activities",
        ["planned_activity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_work_sessions_planned_activity_id",
        "work_sessions",
        ["planned_activity_id"],
    )

    op.drop_constraint(
        "work_participations_session_id_fkey",
        "work_participations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_work_participations_session_id",
        "work_participations",
        "work_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "work_participations",
        sa.Column("actual_team_sequence", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "work_participations",
        sa.Column("pair_index", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "work_participations", sa.Column("side", sa.String(length=12), nullable=True)
    )
    op.add_column(
        "work_participations",
        sa.Column("position_order", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_work_participations_geometry",
        "work_participations",
        "(actual_team_sequence IS NULL AND pair_index IS NULL AND side IS NULL "
        "AND position_order IS NULL) OR "
        "(actual_team_sequence > 0 AND pair_index >= 0 "
        "AND side IN ('left', 'right') AND position_order > 0 "
        "AND assigned_role IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_work_participation_position",
        "work_participations",
        ["session_id", "actual_team_sequence", "pair_index", "side"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_work_participation_position", "work_participations", type_="unique"
    )
    op.drop_constraint(
        "ck_work_participations_geometry", "work_participations", type_="check"
    )
    op.drop_column("work_participations", "position_order")
    op.drop_column("work_participations", "side")
    op.drop_column("work_participations", "pair_index")
    op.drop_column("work_participations", "actual_team_sequence")
    op.drop_constraint(
        "fk_work_participations_session_id",
        "work_participations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "work_participations_session_id_fkey",
        "work_participations",
        "work_sessions",
        ["session_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_index("ix_work_sessions_planned_activity_id", table_name="work_sessions")
    op.drop_constraint(
        "fk_work_sessions_planned_activity_id", "work_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_work_sessions_planned_activity_id", "work_sessions", type_="unique"
    )
    op.drop_constraint("uq_work_sessions_public_id", "work_sessions", type_="unique")
    op.drop_constraint(
        "ck_work_sessions_positive_revision", "work_sessions", type_="check"
    )
    op.drop_column("work_sessions", "updated_at")
    op.drop_column("work_sessions", "created_at")
    op.drop_column("work_sessions", "revision")
    op.drop_column("work_sessions", "start_time")
    op.drop_column("work_sessions", "planned_activity_id")
    op.drop_column("work_sessions", "public_id")
    op.drop_column("planned_activities", "actual_not_run")
