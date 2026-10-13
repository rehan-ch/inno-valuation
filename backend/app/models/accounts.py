"""Accounts: organisations, users, memberships, invitations, user tokens, consultant grants.

Foreign key behaviour is deliberate:
- memberships, invitations and consultant grants are deleted with their organisation;
- memberships, user tokens and a consultant's grants are deleted with their user;
- "created by", "invited by" and "granted by" become NULL when that user is deleted, so the
  record itself survives.

Tokens (invitations, email verification, password reset) are stored only as a SHA-256 hex
digest. The raw token exists only in the email link.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.emails import normalise_email
from app.db.base import Base
from app.models._mixins import CreatedAt, Timestamps, UuidPrimaryKey
from app.models.enums import (
    ConsultantGrantScope,
    MembershipRole,
    OrganisationStatus,
    UserTokenPurpose,
    enum_type,
)

DEFAULT_CURRENCY = "USD"  # Product setting, see docs/decisions.md (2026-10-08).

EMAIL_LENGTH = 320  # RFC 5321 maximum (64 local part + @ + 255 domain).
TOKEN_HASH_LENGTH = 64  # SHA-256 hex digest.


def _email_normalised(column: str) -> CheckConstraint:
    return CheckConstraint(f"{column} = lower(btrim({column}))", name=f"{column}_normalised")


class Organisation(UuidPrimaryKey, Timestamps, Base):
    __tablename__ = "organisations"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="country_iso3166"),
    )

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(CHAR(2))  # ISO 3166-1 alpha-2
    size_band: Mapped[str | None] = mapped_column(String(50))
    revenue_band: Mapped[str | None] = mapped_column(String(50))
    founder_names: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    primary_contact_name: Mapped[str | None] = mapped_column(String(200))
    primary_contact_email: Mapped[str | None] = mapped_column(String(EMAIL_LENGTH))
    currency: Mapped[str] = mapped_column(
        CHAR(3), default=DEFAULT_CURRENCY, server_default=DEFAULT_CURRENCY
    )
    status: Mapped[OrganisationStatus] = mapped_column(
        enum_type(OrganisationStatus, "status"),
        default=OrganisationStatus.ACTIVE,
        server_default=OrganisationStatus.ACTIVE.value,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class User(UuidPrimaryKey, Timestamps, Base):
    """A person who signs in. Not tied to one organisation: memberships link the two.

    ``password_hash`` and ``google_sub`` are both nullable so either sign-in method (or
    both) fits; the check only requires at least one (open-questions Q14).
    """

    __tablename__ = "users"
    __table_args__ = (
        _email_normalised("email"),
        CheckConstraint(
            "password_hash IS NOT NULL OR google_sub IS NOT NULL", name="has_sign_in_method"
        ),
        CheckConstraint(
            "(terms_version IS NULL) = (terms_accepted_at IS NULL)", name="terms_complete"
        ),
        CheckConstraint("session_version >= 1", name="session_version_positive"),
    )

    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    email_verified_at: Mapped[datetime | None]
    # Disabled users cannot sign in.
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Platform staff (tech admin) span organisations, so this is a user flag, not a role.
    is_platform_admin: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    terms_accepted_at: Mapped[datetime | None]
    terms_version: Mapped[str | None] = mapped_column(String(50))
    last_login_at: Mapped[datetime | None]
    # Every session JWT carries the version it was issued under. Raising it (password
    # change, password reset, account disable) ends all existing sessions at once.
    session_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        return normalise_email(value)


class Membership(UuidPrimaryKey, Timestamps, Base):
    """A user's role in one organisation. The unique (organisation_id, user_id) index also
    serves lookups by organisation."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organisation_id", "user_id"),)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MembershipRole] = mapped_column(enum_type(MembershipRole, "role"))

    organisation: Mapped[Organisation] = relationship()
    user: Mapped[User] = relationship()


class Invitation(UuidPrimaryKey, CreatedAt, Base):
    """An invitation to join an organisation. At most one pending invitation per email."""

    __tablename__ = "invitations"
    __table_args__ = (
        _email_normalised("email"),
        CheckConstraint("accepted_at IS NULL OR revoked_at IS NULL", name="accepted_or_revoked"),
        Index(
            "uq_invitations_pending_organisation_id_email",
            "organisation_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH))
    role: Mapped[MembershipRole] = mapped_column(enum_type(MembershipRole, "role"))
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), unique=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    organisation: Mapped[Organisation] = relationship()

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        return normalise_email(value)


class UserToken(UuidPrimaryKey, CreatedAt, Base):
    """A single-use token for email verification or password reset."""

    __tablename__ = "user_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[UserTokenPurpose] = mapped_column(enum_type(UserTokenPurpose, "purpose"))
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()


class ConsultantGrant(UuidPrimaryKey, CreatedAt, Base):
    """The only way a consultant sees an organisation's data (open-questions Q12).

    The client's admin invites the consultant by email and chooses when access ends
    (``expires_at`` is required). ``consultant_user_id`` is set when the consultant accepts.
    """

    __tablename__ = "consultant_grants"
    __table_args__ = (
        _email_normalised("consultant_email"),
        CheckConstraint(
            "accepted_at IS NULL OR consultant_user_id IS NOT NULL", name="accepted_has_user"
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True
    )
    consultant_email: Mapped[str] = mapped_column(String(EMAIL_LENGTH))
    consultant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    scope: Mapped[ConsultantGrantScope] = mapped_column(
        enum_type(ConsultantGrantScope, "scope"),
        default=ConsultantGrantScope.READ_RESULTS,
        server_default=ConsultantGrantScope.READ_RESULTS.value,
    )
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    accepted_at: Mapped[datetime | None]

    organisation: Mapped[Organisation] = relationship()

    @validates("consultant_email")
    def _normalise_email(self, _key: str, value: str) -> str:
        return normalise_email(value)
