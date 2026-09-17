"""add planned team lineups

Revision ID: 9fa6b3d1c204
Revises: 83ee450cd525
Create Date: 2026-09-17 19:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9fa6b3d1c204"
down_revision: str | None = "83ee450cd525"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planned_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planned_activity_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("team_size", sa.SmallInteger(), nullable=False),
        sa.Column("display_label", sa.String(length=80), nullable=True),
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
        sa.CheckConstraint("sequence > 0", name="ck_planned_teams_sequence"),
        sa.CheckConstraint(
            "team_size IN (4, 6, 8, 10, 12)", name="ck_planned_teams_size"
        ),
        sa.ForeignKeyConstraint(
            ["planned_activity_id"], ["planned_activities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "planned_activity_id", "sequence", name="uq_planned_team_sequence"
        ),
        sa.UniqueConstraint(
            "id", "planned_activity_id", name="uq_planned_team_activity_identity"
        ),
    )
    op.create_index(
        "ix_planned_teams_planned_activity_id",
        "planned_teams",
        ["planned_activity_id"],
    )

    op.create_table(
        "planned_team_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("planned_team_id", sa.Integer(), nullable=False),
        sa.Column("planned_activity_id", sa.Integer(), nullable=False),
        sa.Column("dog_id", sa.Integer(), nullable=False),
        sa.Column("pair_index", sa.SmallInteger(), nullable=False),
        sa.Column("side", sa.String(length=12), nullable=False),
        sa.Column("harness_role", sa.String(length=20), nullable=False),
        sa.Column("position_order", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("pair_index >= 0", name="ck_planned_team_slots_pair_index"),
        sa.CheckConstraint("position_order > 0", name="ck_planned_team_slots_order"),
        sa.CheckConstraint(
            "side IN ('left', 'right')", name="ck_planned_team_slots_side"
        ),
        sa.CheckConstraint(
            "harness_role IN ('lead', 'team', 'wheel')",
            name="ck_planned_team_slots_role",
        ),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["planned_team_id", "planned_activity_id"],
            ["planned_teams.id", "planned_teams.planned_activity_id"],
            ondelete="CASCADE",
            name="fk_planned_team_slots_team_activity",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "planned_team_id",
            "pair_index",
            "side",
            name="uq_planned_team_slot_position",
        ),
        sa.UniqueConstraint(
            "planned_team_id",
            "position_order",
            name="uq_planned_team_slot_order",
        ),
        sa.UniqueConstraint(
            "planned_activity_id",
            "dog_id",
            name="uq_planned_team_slot_dog_per_activity",
        ),
    )
    op.create_index(
        "ix_planned_team_slots_planned_team_id",
        "planned_team_slots",
        ["planned_team_id"],
    )
    op.create_index(
        "ix_planned_team_slots_planned_activity_id",
        "planned_team_slots",
        ["planned_activity_id"],
    )
    op.create_index("ix_planned_team_slots_dog_id", "planned_team_slots", ["dog_id"])


def downgrade() -> None:
    op.drop_index("ix_planned_team_slots_dog_id", table_name="planned_team_slots")
    op.drop_index(
        "ix_planned_team_slots_planned_activity_id",
        table_name="planned_team_slots",
    )
    op.drop_index(
        "ix_planned_team_slots_planned_team_id", table_name="planned_team_slots"
    )
    op.drop_table("planned_team_slots")
    op.drop_index("ix_planned_teams_planned_activity_id", table_name="planned_teams")
    op.drop_table("planned_teams")
