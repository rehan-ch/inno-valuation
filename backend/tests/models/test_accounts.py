"""Database constraints and foreign key behaviour of the accounts and audit tables.

DB-level checks are exercised with raw SQL where the ORM would reject the value first, so
the test proves the database itself refuses it.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg import errors as pg_errors
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ConsultantGrant,
    Invitation,
    Membership,
    Organisation,
    User,
    UserToken,
)
from app.models.enums import ConsultantGrantScope, MembershipRole, OrganisationStatus
from tests.factories import (
    AuditEventFactory,
    ConsultantGrantFactory,
    InvitationFactory,
    MembershipFactory,
    OrganisationFactory,
    UserFactory,
    UserTokenFactory,
    fake_token_hash,
)


def _constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


@contextmanager
def expect_violation(db: Session, constraint: str) -> Iterator[None]:
    """The block must fail on exactly ``constraint``. Rolls back to a savepoint after."""
    with pytest.raises(IntegrityError) as info, db.begin_nested():  # noqa: PT012
        # The caller's block runs here, then the flush that hits the constraint.
        yield
        db.flush()
    assert _constraint_name(info.value) == constraint


def _insert(db: Session, table: str, **values: Any) -> None:
    columns = ", ".join(["id", *values])
    params = ", ".join(["gen_random_uuid()", *(f":{key}" for key in values)])
    # Table and column names are fixed in this file; values are bound parameters.
    db.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({params})"), values)  # noqa: S608


def _count(db: Session, model: type[Any], **filters: Any) -> int:
    stmt = select(func.count()).select_from(model).filter_by(**filters)
    return int(db.execute(stmt).scalar_one())


# Organisations


def test_organisation_defaults(db: Session) -> None:
    org = OrganisationFactory.create()
    db.refresh(org)
    assert org.currency == "USD"
    assert org.status is OrganisationStatus.ACTIVE
    assert org.created_at.tzinfo is not None
    assert org.updated_at.tzinfo is not None


@pytest.mark.parametrize("currency", ["usd", "US", "U5D"])
def test_bad_currency_rejected(db: Session, currency: str) -> None:
    with expect_violation(db, "ck_organisations_currency_iso4217"):
        OrganisationFactory.create(currency=currency)


def test_other_currency_accepted(db: Session) -> None:
    assert OrganisationFactory.create(currency="EUR").currency == "EUR"


@pytest.mark.parametrize("country", ["gb", "G1"])
def test_bad_country_rejected(db: Session, country: str) -> None:
    with expect_violation(db, "ck_organisations_country_iso3166"):
        OrganisationFactory.create(country=country)


def test_country_is_optional(db: Session) -> None:
    assert OrganisationFactory.create(country=None).country is None
    assert OrganisationFactory.create(country="GB").country == "GB"


def test_blank_name_rejected(db: Session) -> None:
    with expect_violation(db, "ck_organisations_name_not_blank"):
        OrganisationFactory.create(name="   ")


def test_bad_status_rejected_by_database(db: Session) -> None:
    with expect_violation(db, "ck_organisations_status"):
        _insert(db, "organisations", name="Acme", status="deleted")


# Users


def test_email_stored_lowercased(db: Session) -> None:
    user = UserFactory.create(email="  Ana.Silva@Example.COM ")
    assert user.email == "ana.silva@example.com"


def test_email_unique_ignoring_case(db: Session) -> None:
    UserFactory.create(email="ana@example.com")
    with expect_violation(db, "uq_users_email"):
        UserFactory.create(email="ANA@Example.com")


def test_database_rejects_mixed_case_email(db: Session) -> None:
    with expect_violation(db, "ck_users_email_normalised"):
        _insert(db, "users", email="Ana@example.com", name="Ana", password_hash="x")


def test_user_defaults(db: Session) -> None:
    user = UserFactory.create()
    db.refresh(user)
    assert user.is_active is True
    assert user.is_platform_admin is False
    assert user.email_verified_at is None


def test_user_needs_a_sign_in_method(db: Session) -> None:
    with expect_violation(db, "ck_users_has_sign_in_method"):
        UserFactory.create(password_hash=None, google_sub=None)


def test_google_only_user_allowed(db: Session) -> None:
    user = UserFactory.create(password_hash=None, google_sub="google-123")
    assert user.password_hash is None


def test_google_sub_unique(db: Session) -> None:
    UserFactory.create(google_sub="google-123")
    with expect_violation(db, "uq_users_google_sub"):
        UserFactory.create(google_sub="google-123")


def test_terms_version_and_time_go_together(db: Session) -> None:
    with expect_violation(db, "ck_users_terms_complete"):
        UserFactory.create(terms_version="2026-10", terms_accepted_at=None)
    user = UserFactory.create(terms_version="2026-10", terms_accepted_at=datetime.now(UTC))
    assert user.terms_version == "2026-10"


# Memberships


def test_duplicate_membership_rejected(db: Session) -> None:
    membership = MembershipFactory.create()
    with expect_violation(db, "uq_memberships_organisation_id_user_id"):
        MembershipFactory.create(
            organisation=membership.organisation, user=membership.user, role=MembershipRole.ADMIN
        )


def test_user_can_belong_to_two_organisations(db: Session) -> None:
    user = UserFactory.create()
    MembershipFactory.create(user=user)
    MembershipFactory.create(user=user)
    assert _count(db, Membership, user_id=user.id) == 2


@pytest.mark.parametrize("role", ["consultant", "tech_admin", "OWNER", ""])
def test_bad_role_rejected_by_database(db: Session, role: str) -> None:
    org, user = OrganisationFactory.create(), UserFactory.create()
    with expect_violation(db, "ck_memberships_role"):
        _insert(db, "memberships", organisation_id=org.id, user_id=user.id, role=role)


def test_every_role_accepted(db: Session) -> None:
    org = OrganisationFactory.create()
    for role in MembershipRole:
        assert MembershipFactory.create(organisation=org, role=role).role is role


# Invitations


def test_duplicate_pending_invitation_rejected(db: Session) -> None:
    invitation = InvitationFactory.create(email="bo@example.com")
    with expect_violation(db, "uq_invitations_pending_organisation_id_email"):
        InvitationFactory.create(organisation=invitation.organisation, email="Bo@Example.com")


def test_new_invitation_allowed_after_accept_or_revoke(db: Session) -> None:
    first = InvitationFactory.create(email="bo@example.com", accepted_at=datetime.now(UTC))
    org = first.organisation
    InvitationFactory.create(organisation=org, email="bo@example.com", revoked_at=datetime.now(UTC))
    InvitationFactory.create(organisation=org, email="bo@example.com")
    assert _count(db, Invitation, organisation_id=org.id) == 3


def test_same_email_pending_in_two_organisations(db: Session) -> None:
    InvitationFactory.create(email="bo@example.com")
    InvitationFactory.create(email="bo@example.com")
    assert _count(db, Invitation, email="bo@example.com") == 2


def test_invitation_cannot_be_accepted_and_revoked(db: Session) -> None:
    now = datetime.now(UTC)
    with expect_violation(db, "ck_invitations_accepted_or_revoked"):
        InvitationFactory.create(accepted_at=now, revoked_at=now)


def test_invitation_token_hash_unique(db: Session) -> None:
    token_hash = fake_token_hash()
    InvitationFactory.create(token_hash=token_hash)
    with expect_violation(db, "uq_invitations_token_hash"):
        InvitationFactory.create(token_hash=token_hash)


def test_database_rejects_mixed_case_invitation_email(db: Session) -> None:
    org = OrganisationFactory.create()
    with expect_violation(db, "ck_invitations_email_normalised"):
        _insert(
            db,
            "invitations",
            organisation_id=org.id,
            email="Bo@example.com",
            role="member",
            token_hash=fake_token_hash(),
            expires_at=datetime.now(UTC),
        )


# User tokens


def test_user_token_hash_unique(db: Session) -> None:
    token_hash = fake_token_hash()
    UserTokenFactory.create(token_hash=token_hash)
    with expect_violation(db, "uq_user_tokens_token_hash"):
        UserTokenFactory.create(token_hash=token_hash)


def test_bad_token_purpose_rejected_by_database(db: Session) -> None:
    user = UserFactory.create()
    with expect_violation(db, "ck_user_tokens_purpose"):
        _insert(
            db,
            "user_tokens",
            user_id=user.id,
            purpose="login",
            token_hash=fake_token_hash(),
            expires_at=datetime.now(UTC),
        )


# Consultant grants


def test_grant_defaults_to_read_results(db: Session) -> None:
    grant = ConsultantGrantFactory.create(consultant_email="Amy@Example.com")
    assert grant.scope is ConsultantGrantScope.READ_RESULTS
    assert grant.consultant_email == "amy@example.com"


def test_grant_needs_an_end_date(db: Session) -> None:
    with pytest.raises(IntegrityError) as info, db.begin_nested():
        ConsultantGrantFactory.create(expires_at=None)
    assert isinstance(info.value.orig, pg_errors.NotNullViolation)


def test_accepted_grant_needs_a_consultant_user(db: Session) -> None:
    with expect_violation(db, "ck_consultant_grants_accepted_has_user"):
        ConsultantGrantFactory.create(accepted_at=datetime.now(UTC), consultant_user_id=None)
    consultant = UserFactory.create()
    grant = ConsultantGrantFactory.create(
        accepted_at=datetime.now(UTC), consultant_user_id=consultant.id
    )
    assert grant.consultant_user_id == consultant.id


def test_bad_grant_scope_rejected_by_database(db: Session) -> None:
    org = OrganisationFactory.create()
    with expect_violation(db, "ck_consultant_grants_scope"):
        _insert(
            db,
            "consultant_grants",
            organisation_id=org.id,
            consultant_email="amy@example.com",
            scope="write_everything",
            expires_at=datetime.now(UTC),
        )


# Foreign key behaviour


def test_deleting_organisation_cascades_to_access_rows(db: Session) -> None:
    org = OrganisationFactory.create()
    MembershipFactory.create(organisation=org)
    InvitationFactory.create(organisation=org)
    ConsultantGrantFactory.create(organisation=org)
    org_id = org.id
    db.execute(delete(Organisation).where(Organisation.id == org_id))
    db.expire_all()
    for model in (Membership, Invitation, ConsultantGrant):
        assert _count(db, model, organisation_id=org_id) == 0


def test_audit_events_block_organisation_delete(db: Session) -> None:
    org = OrganisationFactory.create()
    AuditEventFactory.create(organisation_id=org.id, action="organisation.created")
    with expect_violation(db, "fk_audit_events_organisation_id_organisations"):
        db.execute(delete(Organisation).where(Organisation.id == org.id))


def test_deleting_user_keeps_records_they_created(db: Session) -> None:
    user = UserFactory.create()
    org = OrganisationFactory.create(created_by_user_id=user.id)
    invitation = InvitationFactory.create(organisation=org, invited_by_user_id=user.id)
    grant = ConsultantGrantFactory.create(organisation=org, granted_by_user_id=user.id)
    event = AuditEventFactory.create(organisation_id=org.id, actor_user_id=user.id)
    MembershipFactory.create(organisation=org, user=user)
    UserTokenFactory.create(user=user)
    user_id = user.id

    db.execute(delete(User).where(User.id == user_id))
    db.expire_all()

    assert org.created_by_user_id is None
    assert invitation.invited_by_user_id is None
    assert grant.granted_by_user_id is None
    assert event.actor_user_id is None
    assert _count(db, Membership, user_id=user_id) == 0
    assert _count(db, UserToken, user_id=user_id) == 0


def test_deleting_consultant_removes_their_grants(db: Session) -> None:
    consultant = UserFactory.create()
    ConsultantGrantFactory.create(consultant_user_id=consultant.id, accepted_at=datetime.now(UTC))
    db.execute(delete(User).where(User.id == consultant.id))
    assert _count(db, ConsultantGrant, consultant_user_id=consultant.id) == 0


# Audit events


def test_audit_event_without_organisation(db: Session) -> None:
    event = AuditEventFactory.create(actor_user_id=UserFactory.create().id, target_id=uuid.uuid4())
    db.refresh(event)
    assert event.organisation_id is None
    assert event.details == {}
    assert event.created_at.tzinfo is not None


# Sessions and sign-in throttle (0003_auth)


def test_session_version_defaults_to_one(db: Session) -> None:
    user = UserFactory.create()
    db.refresh(user)
    assert user.session_version == 1


def test_session_version_must_be_positive(db: Session) -> None:
    user = UserFactory.create()
    with expect_violation(db, "ck_users_session_version_positive"):
        user.session_version = 0


def test_throttle_count_cannot_be_negative(db: Session) -> None:
    from tests.factories import SignInThrottleFactory  # noqa: PLC0415

    row = SignInThrottleFactory.create()
    with expect_violation(db, "ck_sign_in_throttles_failed_count_not_negative"):
        row.failed_count = -1


def test_throttle_key_is_unique(db: Session) -> None:
    from tests.factories import SignInThrottleFactory  # noqa: PLC0415

    row = SignInThrottleFactory.create()
    with expect_violation(db, "uq_sign_in_throttles_key_hash"):
        SignInThrottleFactory.create(key_hash=row.key_hash)
