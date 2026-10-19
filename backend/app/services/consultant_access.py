"""Consultant access (Amy's decision): the client's admin gives a consultant read-only
access that ends on a date the client chooses, and can change that date or revoke it.

The consultant accepts while signed in with a verified account for the email the access was
given to. No link token is needed: the verified email is the proof. Until accepted,
nothing is visible to them. ``app.services.access`` turns an accepted, live grant into the
read-only ``consultant`` role on every request, so a revoked or ended grant stops access at
once.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.emails import normalise_email
from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.emails.messages import OrganisationEmail
from app.jobs.tasks.emails import send_organisation_email
from app.models import ConsultantGrant, Membership, Organisation, User
from app.models.enums import ConsultantGrantScope, OrganisationStatus
from app.services import members
from app.services.audit import AuditAction, record
from app.services.organisations import lock_organisation, oldest_in_window, too_many_requests

logger = logging.getLogger(__name__)

# Abuse limits, not product rules: each grant emails an address a user types in.
GRANT_LIMIT: Final = 20  # per organisation per day
GRANT_LIMIT_PERIOD: Final = timedelta(days=1)
GRANTER_LIMIT: Final = 40  # per person per day, across all their organisations
# Technical ceiling, not a product rule: the client chooses any end date, but a date near
# year 10000 is stored by Postgres yet cannot be read back, which would break every page
# that lists the grant.
END_DATE_CEILING: Final = timedelta(days=100 * 366)
# How many grants the client's list shows, newest first.
LIST_LIMIT: Final = 200


class GrantStatus(StrEnum):
    WAITING = "waiting"  # not accepted yet
    ACTIVE = "active"
    ENDED = "ended"  # past its end date
    REVOKED = "revoked"


def status_of(grant: ConsultantGrant, now: datetime | None = None) -> GrantStatus:
    if grant.revoked_at is not None:
        return GrantStatus.REVOKED
    if grant.expires_at <= (now or datetime.now(UTC)):
        return GrantStatus.ENDED
    return GrantStatus.ACTIVE if grant.accepted_at is not None else GrantStatus.WAITING


def _check_end_date(expires_at: datetime, now: datetime) -> None:
    if expires_at <= now:
        raise AppError("invalid_end_date", "The end date must be in the future.", 400)
    if expires_at > now + END_DATE_CEILING:
        raise AppError("invalid_end_date", "The end date is too far in the future.", 400)


def _queue_email(grant_id: uuid.UUID) -> None:
    try:
        send_organisation_email.delay(OrganisationEmail.CONSULTANT_ACCESS.value, str(grant_id))
    except BrokerError:
        logger.exception("Could not queue the email for consultant grant %s", grant_id)


def _find(org: Organisation, db: Session, grant_id: uuid.UUID) -> ConsultantGrant:
    grant = db.scalar(
        select(ConsultantGrant).where(
            ConsultantGrant.id == grant_id, ConsultantGrant.organisation_id == org.id
        )
    )
    if grant is None:
        raise AppError("not_found", "Consultant access not found.", 404)
    return grant


# The client's side


def list_grants(org: Organisation, db: Session) -> list[ConsultantGrant]:
    return list(
        db.scalars(
            select(ConsultantGrant)
            .where(ConsultantGrant.organisation_id == org.id)
            .order_by(ConsultantGrant.created_at.desc(), ConsultantGrant.id)
            .limit(LIST_LIMIT)
        )
    )


def grant(
    org: Organisation, db: Session, *, ctx: OrgContext, email: str, expires_at: datetime
) -> ConsultantGrant:
    """Give ``email`` read-only access until ``expires_at`` and email them. Commits."""
    lock_organisation(db, org)
    members.actor_role(org, db, ctx)
    now = datetime.now(UTC)
    _check_end_date(expires_at, now)
    email = normalise_email(email)
    member = db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organisation_id == org.id, User.email == email)
    )
    if member is not None:
        raise AppError("already_member", "This person is already a member.", 409)
    current = db.scalar(
        select(ConsultantGrant.id).where(
            ConsultantGrant.organisation_id == org.id,
            ConsultantGrant.consultant_email == email,
            ConsultantGrant.revoked_at.is_(None),
            ConsultantGrant.expires_at > now,
        )
    )
    if current is not None:
        raise AppError(
            "access_exists", "This person already has access. Change the end date instead.", 409
        )
    for condition, limit, rule in (
        (
            ConsultantGrant.organisation_id == org.id,
            GRANT_LIMIT,
            f"This organisation has given consultant access {GRANT_LIMIT} times in the last "
            "day, the most allowed.",
        ),
        (
            ConsultantGrant.granted_by_user_id == ctx.user.id,
            GRANTER_LIMIT,
            f"You have given consultant access {GRANTER_LIMIT} times in the last day, "
            "the most allowed.",
        ),
    ):
        in_window = (condition, ConsultantGrant.created_at > now - GRANT_LIMIT_PERIOD)
        recent = db.scalar(select(func.count()).select_from(ConsultantGrant).where(*in_window))
        if (recent or 0) >= limit:
            oldest = oldest_in_window(
                db, select(func.min(ConsultantGrant.created_at)).where(*in_window)
            )
            raise too_many_requests(rule, oldest + GRANT_LIMIT_PERIOD - now)
    new = ConsultantGrant(
        organisation_id=org.id,
        consultant_email=email,
        granted_by_user_id=ctx.user.id,
        scope=ConsultantGrantScope.READ_RESULTS,
        expires_at=expires_at,
    )
    db.add(new)
    db.flush()
    record(
        db,
        AuditAction.CONSULTANT_ACCESS_GRANTED,
        actor=ctx.user,
        organisation_id=org.id,
        target_type="consultant_grant",
        target_id=new.id,
        details={"expires_at": expires_at.isoformat()},
    )
    db.commit()
    _queue_email(new.id)
    return new


def change_end_date(
    org: Organisation,
    db: Session,
    *,
    ctx: OrgContext,
    grant_id: uuid.UUID,
    expires_at: datetime,
) -> ConsultantGrant:
    """Move the end date of access that has not ended. Earlier or later. Commits."""
    lock_organisation(db, org)
    members.actor_role(org, db, ctx)
    now = datetime.now(UTC)
    found = _find(org, db, grant_id)
    if status_of(found, now) in (GrantStatus.ENDED, GrantStatus.REVOKED):
        raise AppError("access_ended", "This access has ended. Give access again instead.", 409)
    _check_end_date(expires_at, now)
    previous = found.expires_at
    found.expires_at = expires_at
    record(
        db,
        AuditAction.CONSULTANT_ACCESS_CHANGED,
        actor=ctx.user,
        organisation_id=org.id,
        target_type="consultant_grant",
        target_id=found.id,
        details={"from": previous.isoformat(), "to": expires_at.isoformat()},
    )
    db.commit()
    return found


def revoke(
    org: Organisation, db: Session, *, ctx: OrgContext, grant_id: uuid.UUID
) -> ConsultantGrant:
    """End access now. Revoking twice changes nothing. Commits."""
    lock_organisation(db, org)
    members.actor_role(org, db, ctx)
    found = _find(org, db, grant_id)
    if found.revoked_at is None:
        found.revoked_at = datetime.now(UTC)
        record(
            db,
            AuditAction.CONSULTANT_ACCESS_REVOKED,
            actor=ctx.user,
            organisation_id=org.id,
            target_type="consultant_grant",
            target_id=found.id,
        )
    db.commit()
    return found


def end_on_joining(org: Organisation, db: Session, *, user: User, now: datetime) -> None:
    """Revoke the user's open consultant access when they join as a member, so removing
    them from the team later leaves no access behind. The caller holds the organisation
    lock and commits."""
    open_grants = db.scalars(
        select(ConsultantGrant).where(
            ConsultantGrant.organisation_id == org.id,
            ConsultantGrant.consultant_email == normalise_email(user.email),
            ConsultantGrant.revoked_at.is_(None),
            ConsultantGrant.expires_at > now,
        )
    ).all()
    for found in open_grants:
        found.revoked_at = now
        record(
            db,
            AuditAction.CONSULTANT_ACCESS_REVOKED,
            actor=user,
            organisation_id=org.id,
            target_type="consultant_grant",
            target_id=found.id,
            details={"reason": "became_member"},
        )


# The consultant's side


def for_consultant(db: Session, user: User) -> list[ConsultantGrant]:
    """The consultant's access that has not ended: accepted grants, plus grants waiting for
    their email, except in organisations where they are a member. Organisation loaded,
    soonest end date first."""
    now = datetime.now(UTC)
    return list(
        db.scalars(
            select(ConsultantGrant)
            .where(
                ConsultantGrant.revoked_at.is_(None),
                ConsultantGrant.expires_at > now,
                or_(
                    and_(
                        ConsultantGrant.consultant_user_id == user.id,
                        ConsultantGrant.accepted_at.is_not(None),
                    ),
                    and_(
                        ConsultantGrant.consultant_email == normalise_email(user.email),
                        ConsultantGrant.accepted_at.is_(None),
                    ),
                ),
                # Where the user is a member, the membership decides.
                ~exists().where(
                    Membership.organisation_id == ConsultantGrant.organisation_id,
                    Membership.user_id == user.id,
                ),
            )
            .options(joinedload(ConsultantGrant.organisation))
            .order_by(ConsultantGrant.expires_at, ConsultantGrant.id)
        )
    )


def accept(db: Session, user: User, *, grant_id: uuid.UUID) -> ConsultantGrant:
    """Accept access given to the user's email. 404 for anything else. Commits.

    Locks the organisation, then the grant (the same order as every team change), and
    checks again under the locks.
    """

    def waiting(lock: bool) -> ConsultantGrant | None:
        query = (
            select(ConsultantGrant)
            .where(
                ConsultantGrant.id == grant_id,
                ConsultantGrant.consultant_email == normalise_email(user.email),
                ConsultantGrant.accepted_at.is_(None),
                ConsultantGrant.revoked_at.is_(None),
                ConsultantGrant.expires_at > datetime.now(UTC),
            )
            .execution_options(populate_existing=True)
        )
        return db.scalar(query.with_for_update() if lock else query)

    found = waiting(lock=False)
    if found is None:
        raise AppError("not_found", "Consultant access not found.", 404)
    org = found.organisation
    lock_organisation(db, org)
    found = waiting(lock=True)
    if found is None:
        raise AppError("not_found", "Consultant access not found.", 404)
    if org.status is OrganisationStatus.ARCHIVED:
        raise AppError(
            "organisation_archived", "This organisation is archived and cannot be opened.", 409
        )
    if members.find_membership(org, db, user.id) is not None:
        raise AppError("already_member", "You are already a member of this organisation.", 409)
    found.consultant_user_id = user.id
    found.accepted_at = datetime.now(UTC)
    record(
        db,
        AuditAction.CONSULTANT_ACCESS_ACCEPTED,
        actor=user,
        organisation_id=org.id,
        target_type="consultant_grant",
        target_id=found.id,
    )
    db.commit()
    return found
