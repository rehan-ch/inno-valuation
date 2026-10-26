"""Readiness review fixes: consensus remembers its participants; new assessments collect.

The result's participant count was counted from live responses at finalising time, and a
response goes when its person is deleted. The consensus row now records the count when
agreeing begins. The status column also defaults to ``collecting`` in the database.

Revision ID: 0009_readiness_participants
Revises: 0008_revoked_sessions
Create Date: 2026-10-26 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_readiness_participants"
down_revision: str | Sequence[str] | None = "0008_revoked_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "readiness_consensus", sa.Column("participant_count", sa.Integer(), nullable=True)
    )
    # Existing rows: count the submitted responses still there. Agreeing could only begin
    # with at least one submission, so a count of 0 means those people were deleted since.
    op.execute(
        """
        UPDATE readiness_consensus AS c
        SET participant_count = GREATEST(
            (
                SELECT count(*) FROM readiness_responses AS r
                WHERE r.assessment_id = c.assessment_id AND r.submitted_at IS NOT NULL
            ),
            1
        )
        """
    )
    op.alter_column("readiness_consensus", "participant_count", nullable=False)
    op.create_check_constraint(
        op.f("ck_readiness_consensus_participant_count_positive"),
        "readiness_consensus",
        "participant_count >= 1",
    )
    op.alter_column("readiness_assessments", "status", server_default=sa.text("'collecting'"))


def downgrade() -> None:
    op.alter_column("readiness_assessments", "status", server_default=None)
    op.drop_constraint(
        op.f("ck_readiness_consensus_participant_count_positive"),
        "readiness_consensus",
        type_="check",
    )
    op.drop_column("readiness_consensus", "participant_count")
