"""auth hardening: contested verification links need a password, throttle counts attempts

``user_tokens.requires_password``: a repeat sign-up for an email whose account is not
verified yet gets a verification link that can only be used together with a new password.
Only ``verify_email`` tokens may set it. Existing rows default to false.

``sign_in_throttles``: ``failed_count`` and ``first_failed_at`` are renamed to
``attempt_count`` and ``window_started_at`` (attempts are now counted before the password is
checked). Renamed in place, so existing rows keep their counts.

Revision ID: 0004_auth_hardening
Revises: 0003_auth
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_auth_hardening"
down_revision: str | Sequence[str] | None = "0003_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_tokens",
        sa.Column(
            "requires_password", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_user_tokens_password_only_for_verify_email"),
        "user_tokens",
        "purpose = 'verify_email' OR NOT requires_password",
    )

    op.drop_constraint(
        op.f("ck_sign_in_throttles_failed_count_not_negative"), "sign_in_throttles", type_="check"
    )
    op.alter_column("sign_in_throttles", "failed_count", new_column_name="attempt_count")
    op.alter_column("sign_in_throttles", "first_failed_at", new_column_name="window_started_at")
    op.create_check_constraint(
        op.f("ck_sign_in_throttles_attempt_count_not_negative"),
        "sign_in_throttles",
        "attempt_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_sign_in_throttles_attempt_count_not_negative"),
        "sign_in_throttles",
        type_="check",
    )
    op.alter_column("sign_in_throttles", "window_started_at", new_column_name="first_failed_at")
    op.alter_column("sign_in_throttles", "attempt_count", new_column_name="failed_count")
    op.create_check_constraint(
        op.f("ck_sign_in_throttles_failed_count_not_negative"),
        "sign_in_throttles",
        "failed_count >= 0",
    )

    op.drop_constraint(
        op.f("ck_user_tokens_password_only_for_verify_email"), "user_tokens", type_="check"
    )
    op.drop_column("user_tokens", "requires_password")
