"""PDF reports (Phase 7, P7.01): one row per report asked for, with the snapshot of
everything it shows and, once drawn, where its file is kept.

Revision ID: 0014_reports
Revises: 0013_advice
Create Date: 2026-11-27 12:05:56.971439

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_reports"
down_revision: str | Sequence[str] | None = "0013_advice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("file_key", sa.String(length=200), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
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
            "(status = 'ready') = (file_key IS NOT NULL AND file_size IS NOT NULL"
            " AND file_sha256 IS NOT NULL)",
            name=op.f("ck_reports_file_when_ready"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'rendering', 'ready', 'failed')", name=op.f("ck_reports_status")
        ),
        sa.CheckConstraint(
            "subject_type IN ('readiness_result', 'iq_assessment')",
            name=op.f("ck_reports_subject_type"),
        ),
        sa.CheckConstraint(
            "file_size IS NULL OR file_size > 0", name=op.f("ck_reports_file_size_positive")
        ),
        sa.CheckConstraint(
            "template_version >= 1", name=op.f("ck_reports_template_version_positive")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_reports_version_positive")),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name=op.f("fk_reports_organisation_id_organisations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_reports_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "version",
            name=op.f("uq_reports_subject_type_subject_id_version"),
        ),
    )
    op.create_index(
        "ix_reports_organisation_id_created_at",
        "reports",
        ["organisation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_reports_organisation_id_subject",
        "reports",
        ["organisation_id", "subject_id", "version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reports_requested_by_user_id"), "reports", ["requested_by_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_requested_by_user_id"), table_name="reports")
    op.drop_index("ix_reports_organisation_id_subject", table_name="reports")
    op.drop_index("ix_reports_organisation_id_created_at", table_name="reports")
    op.drop_table("reports")
