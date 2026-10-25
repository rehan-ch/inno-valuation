"""AI run log (Phase 3, P3.05): one row per AI result, with its prompt and use.

Revision ID: 0007_ai_runs
Revises: 0006_readiness
Create Date: 2026-10-24 23:11:38.079042

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_ai_runs"
down_revision: str | Sequence[str] | None = "0006_readiness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("touchpoint", sa.String(length=50), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("effort", sa.String(length=20), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("response_model", sa.String(length=100), nullable=True),
        sa.Column("response_raw", sa.Text(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("stop_reason", sa.String(length=50), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_micro_usd", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "provider_request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')", name=op.f("ck_ai_runs_status")
        ),
        sa.CheckConstraint(
            "touchpoint IN ('explain_question', 'context_questions', 'propose_iq_scores', "
            "'interpret_results', 'bridge_gaps', 'recommendations', 'report_narrative', "
            "'consultation_nudge')",
            name=op.f("ck_ai_runs_touchpoint"),
        ),
        sa.CheckConstraint("cost_micro_usd >= 0", name=op.f("ck_ai_runs_cost_positive")),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND attempts >= 0",
            name=op.f("ck_ai_runs_counts_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_ai_runs_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_ai_runs_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_runs")),
    )
    op.create_index(
        "ix_ai_runs_organisation_id_subject",
        "ai_runs",
        ["organisation_id", "touchpoint", "subject_type", "subject_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_runs_requested_by_user_id"), "ai_runs", ["requested_by_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_runs_requested_by_user_id"), table_name="ai_runs")
    op.drop_index("ix_ai_runs_organisation_id_subject", table_name="ai_runs")
    op.drop_table("ai_runs")
