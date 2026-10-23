"""Invite people to the active organisation, and accept an invitation.

An invitation is a single-use link sent to one email address. The raw token is derived
from the row id and the secret key (``invitation_token_value``); only its SHA-256 hash is
stored, and the email task rebuilds the link from the id.

- Inviting the same email again replaces the pending invitation (the old link stops
  working), so "resend" is just inviting again.
- Only an owner may invite someone as an owner (see ``app.services.members``).
- Accepting needs a signed-in, verified account with the invited email. A forwarded link
  is useless to anyone else, and the verified email proves the inbox is theirs.
- An invitation counts only while its sender may still give its role: one sent by an admin
  who has since been removed, or an owner invitation from someone no longer an owner, is
  refused.
- Joining ends any consultant access the person had, so removing them later removes all
  access.

Locks are always taken in the same order, organisation row first, then the invitation, so
inviting, cancelling and accepting cannot deadlock or overtake each other.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.emails import normalise_email
from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.core.security import hash_token, invitation_token_value
from app.emails.messages import OrganisationEmail
from app.jobs.tasks.emails import send_organisation_email
from app.models import Invitation, Membership, Organisation, User
from app.models.enums import MembershipRole, OrganisationStatus
from app.services import consultant_access, members
from app.services.audit import AuditAction, record
from app.services.organisations import enforce_limit, lock_organisation
from app.services.team_emails import INVITATION_LIFETIME, invitation_is_pending

logger = logging.getLogger(__name__)

# Abuse limits, not product rules: invitations send email to addresses a user types in.
INVITE_LIMIT: Final = 50  # per organisation per day
INVITE_LIMIT_PERIOD: Final = timedelta(days=1)
INVITER_LIMIT: Final = 100  # per person per day, across all their organisations
RECIPIENT_LIMIT: Final = 3  # per (organisation, email) per hour, so "resend" stays possible
RECIPIENT_LIMIT_PERIOD: Final = timedelta(hours=1)
# How many invitations the list shows, newest first.
LIST_LIMIT: Final = 200


@dataclass(frozen=True)
class PendingInvitation:
    invitation: Invitation
    invited_by_name: str | None


@dataclass(frozen=True)
class InvitationPreview:
    organisation_name: str
    email: str
    role: MembershipRole
    expires_at: datetime


def _invalid() -> AppError:
    return AppError(
        "invalid_invitation",
        "This invitation is not valid or has expired. Ask for a new one.",
        400,
    )


def _queue_email(invitation_id: uuid.UUID) -> None:
    try:
        send_organisation_email.delay(OrganisationEmail.INVITATION.value, str(invitation_id))
    except BrokerError:
        # The invitation is saved; inviting again sends a new link.
        logger.exception("Could not queue the email for invitation %s", invitation_id)


def list_pending(org: Organisation, db: Session) -> list[PendingInvitation]:
    """Invitations not accepted and not revoked, newest first. Expired ones are included
    (the caller shows them as expired) until someone invites that email again."""
    rows = db.execute(
        select(Invitation, User.name)
        .outerjoin(User, User.id == Invitation.invited_by_user_id)
        .where(
            Invitation.organisation_id == org.id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .order_by(Invitation.created_at.desc(), Invitation.id)
        .limit(LIST_LIMIT)
    ).all()
    return [PendingInvitation(invitation=inv, invited_by_name=name) for inv, name in rows]


def invite(
    org: Organisation, db: Session, *, ctx: OrgContext, email: str, role: MembershipRole
) -> Invitation:
    """Invite ``email`` with ``role`` and queue the email. Commits."""
    lock_organisation(db, org)
    members.require_owner_for(members.actor_role(org, db, ctx), role)
    email = normalise_email(email)
    already_member = db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organisation_id == org.id, User.email == email)
    )
    if already_member is not None:
        raise AppError("already_member", "This person is already a member.", 409)
    enforce_limit(
        db,
        Invitation.created_at,
        Invitation.organisation_id == org.id,
        limit=INVITE_LIMIT,
        period=INVITE_LIMIT_PERIOD,
        rule=f"This organisation has sent {INVITE_LIMIT} invitations in the last day, "
        "the most allowed.",
    )
    enforce_limit(
        db,
        Invitation.created_at,
        Invitation.invited_by_user_id == ctx.user.id,
        limit=INVITER_LIMIT,
        period=INVITE_LIMIT_PERIOD,
        rule=f"You have sent {INVITER_LIMIT} invitations in the last day, the most allowed.",
    )
    enforce_limit(
        db,
        Invitation.created_at,
        Invitation.organisation_id == org.id,
        Invitation.email == email,
        limit=RECIPIENT_LIMIT,
        period=RECIPIENT_LIMIT_PERIOD,
        rule=f"This email has been invited {RECIPIENT_LIMIT} times in the last hour, "
        "the most allowed.",
    )

    now = datetime.now(UTC)
    # Replace any pending invitation for this email: only the newest link works.
    db.execute(
        update(Invitation)
        .where(
            Invitation.organisation_id == org.id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session="fetch")
    )
    invitation = Invitation(
        organisation_id=org.id,
        email=email,
        role=role,
        invited_by_user_id=ctx.user.id,
        expires_at=now + INVITATION_LIFETIME,
    )
    # The id is set first because the stored hash is derived from it.
    invitation.id = uuid.uuid4()
    invitation.token_hash = hash_token(invitation_token_value(invitation.id))
    db.add(invitation)
    db.flush()
    record(
        db,
        AuditAction.MEMBER_INVITED,
        actor=ctx.user,
        organisation_id=org.id,
        target_type="invitation",
        target_id=invitation.id,
        details={"role": role.value},
    )
    db.commit()
    _queue_email(invitation.id)
    return invitation


def revoke(org: Organisation, db: Session, *, ctx: OrgContext, invitation_id: uuid.UUID) -> None:
    """Revoke a pending invitation: its link stops working. Commits."""
    lock_organisation(db, org)
    members.actor_role(org, db, ctx)
    invitation = db.scalar(
        select(Invitation)
        .where(
            Invitation.id == invitation_id,
            Invitation.organisation_id == org.id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if invitation is None:
        raise AppError("not_found", "Invitation not found.", 404)
    invitation.revoked_at = datetime.now(UTC)
    record(
        db,
        AuditAction.INVITATION_REVOKED,
        actor=ctx.user,
        organisation_id=org.id,
        target_type="invitation",
        target_id=invitation.id,
    )
    db.commit()


def _find_usable(db: Session, token: str) -> tuple[Invitation, Organisation]:
    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == hash_token(token))
        .execution_options(populate_existing=True)
    )
    if invitation is None or not invitation_is_pending(invitation):
        raise _invalid()
    org = db.get(Organisation, invitation.organisation_id)
    if org is None or org.status is OrganisationStatus.ARCHIVED:
        raise _invalid()
    return invitation, org


def preview(db: Session, *, token: str) -> InvitationPreview:
    """What the accept page shows before the person signs in. Needs the token, which only
    the invited inbox has."""
    invitation, org = _find_usable(db, token)
    return InvitationPreview(
        organisation_name=org.name,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
    )


def accept(db: Session, user: User, *, token: str) -> Organisation:
    """Join the organisation with the invited role. Commits.

    Takes the organisation lock, then the invitation row lock, and checks everything again
    under them, so two clicks at once cannot both succeed and a cancel cannot cross an
    accept. Someone who is already a member keeps their current role; the invitation is
    used up either way.
    """
    _, org = _find_usable(db, token)
    lock_organisation(db, org)
    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == hash_token(token))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if invitation is None or not invitation_is_pending(invitation):
        raise _invalid()
    if normalise_email(user.email) != invitation.email:
        raise AppError(
            "invitation_email_mismatch",
            "This invitation was sent to a different email address. "
            "Sign in with that address to accept it.",
            403,
        )
    if not members.may_give_role(org, db, invitation.invited_by_user_id, invitation.role):
        raise _invalid()
    already_member = members.find_membership(org, db, user.id) is not None
    if not already_member:
        db.add(Membership(organisation_id=org.id, user_id=user.id, role=invitation.role))
    now = datetime.now(UTC)
    invitation.accepted_at = now
    record(
        db,
        AuditAction.INVITATION_ACCEPTED,
        actor=user,
        organisation_id=org.id,
        target_type="invitation",
        target_id=invitation.id,
        details={"role": invitation.role.value, "already_member": already_member},
    )
    consultant_access.end_on_joining(org, db, user=user, now=now)
    db.commit()
    return org
