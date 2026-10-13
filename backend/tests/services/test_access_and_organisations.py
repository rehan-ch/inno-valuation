import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import OrgRole
from app.models import AuditEvent
from app.models.enums import MembershipRole
from app.services import organisations
from app.services.access import resolve_org_access
from tests.factories import (
    ConsultantGrantFactory,
    MembershipFactory,
    OrganisationFactory,
    UserFactory,
)


def test_membership_gives_its_role(db: Session) -> None:
    membership = MembershipFactory.create(role=MembershipRole.COMMITTEE)
    ctx = resolve_org_access(db, membership.user, membership.organisation_id)
    assert ctx is not None
    assert ctx.role is OrgRole.COMMITTEE
    assert ctx.organisation_id == membership.organisation_id
    assert not ctx.is_consultant


def test_no_membership_no_access(db: Session) -> None:
    user = UserFactory.create(is_platform_admin=True)
    org = OrganisationFactory.create()
    assert resolve_org_access(db, user, org.id) is None
    assert resolve_org_access(db, user, uuid.uuid4()) is None


def test_live_grant_gives_consultant(db: Session) -> None:
    consultant = UserFactory.create()
    grant = ConsultantGrantFactory.create(
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    ctx = resolve_org_access(db, consultant, grant.organisation_id)
    assert ctx is not None
    assert ctx.is_consultant

    grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert resolve_org_access(db, consultant, grant.organisation_id) is None


def test_membership_wins_over_a_grant(db: Session) -> None:
    membership = MembershipFactory.create(role=MembershipRole.ADMIN)
    ConsultantGrantFactory.create(
        organisation=membership.organisation,
        consultant_email=membership.user.email,
        consultant_user_id=membership.user_id,
        accepted_at=datetime.now(UTC),
    )
    ctx = resolve_org_access(db, membership.user, membership.organisation_id)
    assert ctx is not None
    assert ctx.role is OrgRole.ADMIN


def test_update_profile_audits_field_names_only(db: Session) -> None:
    org = OrganisationFactory.create(name="Before", currency="USD")
    actor = UserFactory.create()
    organisations.update_profile(
        org, db, actor=actor, changes={"name": "After", "currency": "USD", "industry": "Retail"}
    )
    assert (org.name, org.industry) == ("After", "Retail")
    [event] = db.scalars(select(AuditEvent).where(AuditEvent.organisation_id == org.id))
    assert event.details == {"fields": ["industry", "name"]}
    assert "After" not in str(event.details)


def test_update_profile_without_changes_writes_no_audit(db: Session) -> None:
    org = OrganisationFactory.create(name="Same")
    organisations.update_profile(org, db, actor=UserFactory.create(), changes={"name": "Same"})
    assert db.scalars(select(AuditEvent).where(AuditEvent.organisation_id == org.id)).all() == []


def test_update_profile_refuses_other_fields(db: Session) -> None:
    org = OrganisationFactory.create()
    with pytest.raises(ValueError, match="status"):
        organisations.update_profile(
            org, db, actor=UserFactory.create(), changes={"status": "archived"}
        )
