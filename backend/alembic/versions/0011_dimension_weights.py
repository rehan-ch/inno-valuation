"""Dimension importance (Phase 4, P4.08): one row per change of an organisation's weights.

Revision ID: 0011_dimension_weights
Revises: 0010_ideas
Create Date: 2026-11-03 09:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_dimension_weights"
down_revision: str | Sequence[str] | None = "0010_ideas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dimension_weights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("set_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT jsonb_path_exists(weights, 'strict $.* ? (@.type() != \"string\")')",
            name=op.f("ck_dimension_weights_weights_are_strings"),
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_dimension_weights_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["set_by_user_id"],
            ["users.id"],
            name=op.f("fk_dimension_weights_set_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dimension_weights")),
    )
    op.create_index(
        "ix_dimension_weights_organisation_id_created_at",
        "dimension_weights",
        ["organisation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dimension_weights_set_by_user_id"),
        "dimension_weights",
        ["set_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dimension_weights_set_by_user_id"), table_name="dimension_weights")
    op.drop_index("ix_dimension_weights_organisation_id_created_at", table_name="dimension_weights")
    op.drop_table("dimension_weights")
