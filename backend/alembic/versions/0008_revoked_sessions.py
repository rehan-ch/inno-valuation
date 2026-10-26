"""revoked sessions: sign-out ends the session on the server too

``revoked_sessions``: one row per session ended by sign-out before its own expiry, keyed by
the random session id (``sid``) carried in the session JWT. Rows for sessions that would
have expired anyway are purged on sign-out. No organisation data.

Revision ID: 0008_revoked_sessions
Revises: 0007_ai_runs
Create Date: 2026-10-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_revoked_sessions"
down_revision: str | Sequence[str] | None = "0007_ai_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_revoked_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_revoked_sessions")),
        sa.UniqueConstraint("sid", name=op.f("uq_revoked_sessions_sid")),
    )
    op.create_index(
        op.f("ix_revoked_sessions_user_id"), "revoked_sessions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_revoked_sessions_user_id"), table_name="revoked_sessions")
    op.drop_table("revoked_sessions")
