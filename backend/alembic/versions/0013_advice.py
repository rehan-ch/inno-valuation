"""AI advice (Phase 6, P6.01): interpretations and recommendations, each linked to its AI
run; and what a run's check needs beyond its subject (``ai_runs.params``).

Revision ID: 0013_advice
Revises: 0012_targets
Create Date: 2026-11-15 23:21:39.456733

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_advice"
down_revision: str | Sequence[str] | None = "0012_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interpretations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "subject_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("per_dimension", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "subject_type IN ('readiness_result', 'iq_assessment')",
            name=op.f("ck_interpretations_subject_type"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_interpretations_version_positive")),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_interpretations_ai_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_interpretations_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interpretations")),
        sa.UniqueConstraint("ai_run_id", name=op.f("uq_interpretations_ai_run_id")),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "version",
            name=op.f("uq_interpretations_subject_type_subject_id_version"),
        ),
    )
    op.create_index(
        "ix_interpretations_organisation_id_subject",
        "interpretations",
        ["organisation_id", "subject_id"],
        unique=False,
    )
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "subject_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dimension_key", sa.String(length=50), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("fixed_text", sa.Text(), nullable=False),
        sa.Column("ai_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "subject_type IN ('readiness_result', 'iq_assessment')",
            name=op.f("ck_recommendations_subject_type"),
        ),
        sa.CheckConstraint(
            "priority_rank >= 1", name=op.f("ck_recommendations_priority_rank_positive")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_recommendations_version_positive")),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_recommendations_ai_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_recommendations_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
        sa.UniqueConstraint(
            "ai_run_id", "dimension_key", name=op.f("uq_recommendations_ai_run_id_dimension_key")
        ),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "version",
            "dimension_key",
            name=op.f("uq_recommendations_subject_version_dimension_key"),
        ),
    )
    op.create_index(
        "ix_recommendations_organisation_id_subject",
        "recommendations",
        ["organisation_id", "subject_id"],
        unique=False,
    )
    op.add_column(
        "ai_runs", sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ai_runs", "params")
    op.drop_index("ix_recommendations_organisation_id_subject", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_interpretations_organisation_id_subject", table_name="interpretations")
    op.drop_table("interpretations")
