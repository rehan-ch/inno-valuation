"""Enumerations stored in the database, plus the column type that stores them.

Values are stored as short strings with a CHECK constraint (not native Postgres enums),
so adding a value is a plain constraint change in a migration.
"""

from enum import StrEnum

from sqlalchemy import Enum


class MembershipRole(StrEnum):
    """A user's role inside one organisation.

    Platform staff are not a role here (``User.is_platform_admin``), and a consultant is
    never a member (``ConsultantGrant``).
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    COMMITTEE = "committee"
    # PROVISIONAL: see open-questions Q13. An investor is a role inside one company's
    # account (option a). Option b would need an investor workspace across organisations.
    INVESTOR = "investor"


class OrganisationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class UserTokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"  # noqa: S105  (a purpose name, not a password)


class ConsultantGrantScope(StrEnum):
    READ_RESULTS = "read_results"


class ReadinessStatus(StrEnum):
    """The life of a readiness assessment, left to right. It never moves backwards.

    ``draft`` is just created; ``collecting`` takes each person's answers; ``consensus``
    is the facilitator setting the agreed answers (Amy Q5); ``final`` is scored and
    immutable.
    """

    DRAFT = "draft"
    COLLECTING = "collecting"
    CONSENSUS = "consensus"
    FINAL = "final"


class AiTouchpoint(StrEnum):
    """The 8 places AI is used. Each one has its model settings in config/ai.yml."""

    EXPLAIN_QUESTION = "explain_question"
    CONTEXT_QUESTIONS = "context_questions"
    PROPOSE_IQ_SCORES = "propose_iq_scores"
    INTERPRET_RESULTS = "interpret_results"
    BRIDGE_GAPS = "bridge_gaps"
    RECOMMENDATIONS = "recommendations"
    REPORT_NARRATIVE = "report_narrative"
    CONSULTATION_NUDGE = "consultation_nudge"


class AiRunStatus(StrEnum):
    """One AI run, left to right: queued, running, then succeeded or failed for good."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def enum_type(enum_cls: type[StrEnum], name: str, length: int = 20) -> Enum:
    """A VARCHAR column with a CHECK constraint named ``ck_<table>_<name>``.

    Stores the enum values (``"owner"``), not the member names (``"OWNER"``).
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )
