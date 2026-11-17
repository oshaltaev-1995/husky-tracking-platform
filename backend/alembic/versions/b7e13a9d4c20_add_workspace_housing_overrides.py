"""add reference-date workspace housing overrides

Revision ID: b7e13a9d4c20
Revises: 5c82f32e5d8a
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e13a9d4c20"
down_revision: str | None = "5c82f32e5d8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "demo_workspaces",
        sa.Column("housing_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_demo_workspaces_housing_revision",
        "demo_workspaces",
        "housing_revision >= 0",
    )
    op.create_table(
        "demo_workspace_housing_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("dog_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["demo_workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["location_id"], ["kennel_locations.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "dog_id",
            "effective_date",
            name="uq_workspace_housing_dog_date",
        ),
    )
    for column in ("workspace_id", "dog_id", "location_id"):
        op.create_index(
            f"ix_demo_workspace_housing_overrides_{column}",
            "demo_workspace_housing_overrides",
            [column],
        )


def downgrade() -> None:
    # Only the temporary workspace projection is lost. Canonical housing is untouched.
    op.drop_table("demo_workspace_housing_overrides")
    op.drop_constraint(
        "ck_demo_workspaces_housing_revision", "demo_workspaces", type_="check"
    )
    op.drop_column("demo_workspaces", "housing_revision")
