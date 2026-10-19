"""team: index consultant grants by email

A consultant accepts access while signed in with the email it was given to, so the
"access waiting for you" lookup filters ``consultant_grants`` by ``consultant_email``.

Revision ID: 0005_team
Revises: 0004_auth_hardening
Create Date: 2026-10-15

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_team"
down_revision: str | Sequence[str] | None = "0004_auth_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_consultant_grants_consultant_email"),
        "consultant_grants",
        ["consultant_email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_consultant_grants_consultant_email"), table_name="consultant_grants")
