"""Targets per dimension (Phase 5, P5.06): one row per change and per scale.

Revision ID: 0012_targets
Revises: 0011_dimension_weights
Create Date: 2026-11-10 10:24:15.737651

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_targets"
down_revision: str | Sequence[str] | None = "0011_dimension_weights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dimension_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("scale", sa.String(length=20), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("targets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("set_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scale IN ('readiness', 'iq')", name=op.f("ck_dimension_targets_target_scale")
        ),
        sa.CheckConstraint(
            "NOT jsonb_path_exists(targets, 'strict $.* ? (@.type() != \"number\")')",
            name=op.f("ck_dimension_targets_targets_are_numbers"),
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_dimension_targets_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["set_by_user_id"],
            ["users.id"],
            name=op.f("fk_dimension_targets_set_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dimension_targets")),
    )
    op.create_index(
        "ix_dimension_targets_organisation_id_scale_created_at",
        "dimension_targets",
        ["organisation_id", "scale", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dimension_targets_set_by_user_id"),
        "dimension_targets",
        ["set_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dimension_targets_set_by_user_id"), table_name="dimension_targets")
    op.drop_index(
        "ix_dimension_targets_organisation_id_scale_created_at", table_name="dimension_targets"
    )
    op.drop_table("dimension_targets")
