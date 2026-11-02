"""Ideas and IQ assessments (Phase 4, P4.01): ideas, assessments, dimension scores.

Revision ID: 0010_ideas
Revises: 0009_readiness_participants
Create Date: 2026-11-02 14:12:45.451276

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_ideas"
down_revision: str | Sequence[str] | None = "0009_readiness_participants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ideas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("target_market", sa.Text(), nullable=True),
        sa.Column("uniqueness", sa.Text(), nullable=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column(
            "stage",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("investment_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("expected_value_minor", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_ideas_title_not_blank")),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_ideas_currency_iso4217")),
        sa.CheckConstraint(
            "stage IN ('idea', 'concept', 'prototype', 'pilot', 'launched')",
            name=op.f("ck_ideas_idea_stage"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'assessed')", name=op.f("ck_ideas_idea_status")
        ),
        sa.CheckConstraint(
            "expected_value_minor IS NULL OR expected_value_minor >= 0",
            name=op.f("ck_ideas_expected_value_positive"),
        ),
        sa.CheckConstraint(
            "investment_minor IS NULL OR investment_minor >= 0",
            name=op.f("ck_ideas_investment_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_ideas_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_ideas_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ideas")),
    )
    op.create_index(
        op.f("ix_ideas_created_by_user_id"), "ideas", ["created_by_user_id"], unique=False
    )
    op.create_index(
        "ix_ideas_organisation_id_created_at",
        "ideas",
        ["organisation_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "iq_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("idea_id", sa.Uuid(), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'proposed'"),
            nullable=False,
        ),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("weights_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("iq", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("category_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priorities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("investment_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), nullable=True),
        sa.Column("vfm_per_point", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'confirmed') = (confirmed_at IS NOT NULL AND iq IS NOT NULL)",
            name=op.f("ck_iq_assessments_confirmed_is_scored"),
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'confirmed', 'superseded')",
            name=op.f("ck_iq_assessments_iq_assessment_status"),
        ),
        sa.CheckConstraint(
            "investment_minor IS NULL OR investment_minor >= 0",
            name=op.f("ck_iq_assessments_investment_positive"),
        ),
        sa.CheckConstraint(
            "iq IS NULL OR (iq >= 0 AND iq <= 100)", name=op.f("ck_iq_assessments_iq_0_to_100")
        ),
        sa.CheckConstraint(
            "vfm_per_point IS NULL OR vfm_per_point >= 0",
            name=op.f("ck_iq_assessments_vfm_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_iq_assessments_ai_run_id_ai_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_iq_assessments_confirmed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["idea_id"],
            ["ideas.id"],
            name=op.f("fk_iq_assessments_idea_id_ideas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_iq_assessments_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_iq_assessments_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_iq_assessments")),
    )
    op.create_index(
        op.f("ix_iq_assessments_ai_run_id"), "iq_assessments", ["ai_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_iq_assessments_confirmed_by_user_id"),
        "iq_assessments",
        ["confirmed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_iq_assessments_idea_id_created_at",
        "iq_assessments",
        ["idea_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_iq_assessments_organisation_id", "iq_assessments", ["organisation_id"], unique=False
    )
    op.create_index(
        op.f("ix_iq_assessments_requested_by_user_id"),
        "iq_assessments",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_table(
        "iq_dimension_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("dimension_key", sa.String(length=50), nullable=False),
        sa.Column("proposed_score", sa.Integer(), nullable=True),
        sa.Column("proposed_rationale", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("proposed_confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("final_score", sa.Integer(), nullable=True),
        sa.Column("level_key", sa.String(length=50), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint(
            "final_score IS NULL OR (final_score >= 1 AND final_score <= 10)",
            name=op.f("ck_iq_dimension_scores_final_score_1_to_10"),
        ),
        sa.CheckConstraint(
            "proposed_confidence IS NULL OR "
            "(proposed_confidence >= 0 AND proposed_confidence <= 1)",
            name=op.f("ck_iq_dimension_scores_confidence_0_to_1"),
        ),
        sa.CheckConstraint(
            "proposed_score IS NULL OR (proposed_score >= 1 AND proposed_score <= 10)",
            name=op.f("ck_iq_dimension_scores_proposed_score_1_to_10"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["iq_assessments.id"],
            name=op.f("fk_iq_dimension_scores_assessment_id_iq_assessments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_iq_dimension_scores_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_iq_dimension_scores_reviewed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_iq_dimension_scores")),
        sa.UniqueConstraint(
            "assessment_id",
            "dimension_key",
            name=op.f("uq_iq_dimension_scores_assessment_id_dimension_key"),
        ),
    )
    op.create_index(
        "ix_iq_dimension_scores_organisation_id",
        "iq_dimension_scores",
        ["organisation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_iq_dimension_scores_reviewed_by_user_id"),
        "iq_dimension_scores",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_iq_dimension_scores_reviewed_by_user_id"), table_name="iq_dimension_scores"
    )
    op.drop_index("ix_iq_dimension_scores_organisation_id", table_name="iq_dimension_scores")
    op.drop_table("iq_dimension_scores")
    op.drop_index(op.f("ix_iq_assessments_requested_by_user_id"), table_name="iq_assessments")
    op.drop_index("ix_iq_assessments_organisation_id", table_name="iq_assessments")
    op.drop_index("ix_iq_assessments_idea_id_created_at", table_name="iq_assessments")
    op.drop_index(op.f("ix_iq_assessments_confirmed_by_user_id"), table_name="iq_assessments")
    op.drop_index(op.f("ix_iq_assessments_ai_run_id"), table_name="iq_assessments")
    op.drop_table("iq_assessments")
    op.drop_index("ix_ideas_organisation_id_created_at", table_name="ideas")
    op.drop_index(op.f("ix_ideas_created_by_user_id"), table_name="ideas")
    op.drop_table("ideas")
