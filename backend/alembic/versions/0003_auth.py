"""auth: users.session_version and the sign_in_throttles table

``users.session_version`` (at least 1) is carried in every session JWT; raising it ends all
of a user's sessions. Existing users start at 1.

``sign_in_throttles`` counts failed password sign-ins per email, keyed by an HMAC of the
normalised email (no email stored), whether or not an account exists. No foreign keys and no
organisation data.

Revision ID: 0003_auth
Revises: 0002_accounts
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_auth"
down_revision: str | Sequence[str] | None = "0002_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_users_session_version_positive"), "users", "session_version >= 1"
    )
    op.create_table(
        "sign_in_throttles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
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
            "failed_count >= 0", name=op.f("ck_sign_in_throttles_failed_count_not_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sign_in_throttles")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_sign_in_throttles_key_hash")),
    )


def downgrade() -> None:
    op.drop_table("sign_in_throttles")
    op.drop_constraint(op.f("ck_users_session_version_positive"), "users", type_="check")
    op.drop_column("users", "session_version")
