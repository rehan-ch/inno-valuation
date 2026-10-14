"""Build team emails (invitation, consultant access) from a row id, for the email task.

Each builder re-loads the row and re-checks it: the invitation is still pending, or the
consultant access is still waiting to be accepted, and the organisation is not archived.
Anything else gives None and nothing is sent. The organisation is always the row's own, so
no id from outside decides which organisation an email speaks for.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy.orm import Session

from app.core.security import invitation_token_value
from app.core.settings import get_settings
from app.emails.messages import EmailMessage, render_consultant_access, render_invitation
from app.models import ConsultantGrant, Invitation, Organisation, User
from app.models.enums import OrganisationStatus

# Product setting: how long an invitation link works.
INVITATION_LIFETIME: Final = timedelta(days=7)


def invitation_is_pending(invitation: Invitation, now: datetime | None = None) -> bool:
    return (
        invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > (now or datetime.now(UTC))
    )


def grant_is_waiting(grant: ConsultantGrant, now: datetime | None = None) -> bool:
    """Not accepted yet, not revoked, not past its end date."""
    return (
        grant.accepted_at is None
        and grant.revoked_at is None
        and grant.expires_at > (now or datetime.now(UTC))
    )


def _active_organisation(db: Session, organisation_id: uuid.UUID) -> Organisation | None:
    org = db.get(Organisation, organisation_id)
    if org is None or org.status is OrganisationStatus.ARCHIVED:
        return None
    return org


def _name_of(db: Session, user_id: uuid.UUID | None) -> str | None:
    user = db.get(User, user_id) if user_id else None
    return user.name if user else None


def build_invitation_email(db: Session, invitation_id: uuid.UUID) -> EmailMessage | None:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or not invitation_is_pending(invitation):
        return None
    org = _active_organisation(db, invitation.organisation_id)
    if org is None:
        return None
    return render_invitation(
        to=invitation.email,
        origin=get_settings().frontend_origin,
        token=invitation_token_value(invitation.id),
        organisation_name=org.name,
        inviter_name=_name_of(db, invitation.invited_by_user_id),
        role=invitation.role.value,
        expires_in=INVITATION_LIFETIME,
    )


def build_consultant_access_email(db: Session, grant_id: uuid.UUID) -> EmailMessage | None:
    grant = db.get(ConsultantGrant, grant_id)
    if grant is None or not grant_is_waiting(grant):
        return None
    org = _active_organisation(db, grant.organisation_id)
    if org is None:
        return None
    return render_consultant_access(
        to=grant.consultant_email,
        origin=get_settings().frontend_origin,
        organisation_name=org.name,
        granter_name=_name_of(db, grant.granted_by_user_id),
        ends_on=grant.expires_at.astimezone(UTC).date(),
    )
