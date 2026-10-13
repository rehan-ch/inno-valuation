"""Resolve a user's access to an organisation: through a membership or a live consultant grant.

This is the one lookup that starts from an organisation id instead of an ``Organisation``:
it is how ``current_org`` and the organisation switcher turn the id stored in the session
into an ``OrgContext``. Nothing else may read an organisation id from a request.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import OrgContext, OrgRole
from app.models import ConsultantGrant, Membership, Organisation, User


def resolve_org_access(db: Session, user: User, organisation_id: uuid.UUID) -> OrgContext | None:
    """The caller's access to the organisation, or None (callers answer 404).

    A membership wins. Otherwise a live consultant grant (accepted, not revoked, not
    expired) gives the read-only ``consultant`` role. ``is_platform_admin`` gives nothing.
    """
    row = db.execute(
        select(Membership, Organisation)
        .join(Organisation, Organisation.id == Membership.organisation_id)
        .where(Membership.organisation_id == organisation_id, Membership.user_id == user.id)
    ).first()
    if row is not None:
        membership, organisation = row
        return OrgContext(
            organisation=organisation,
            user=user,
            role=OrgRole.from_membership(membership.role),
        )

    grant_org = db.scalar(
        select(Organisation)
        .join(ConsultantGrant, ConsultantGrant.organisation_id == Organisation.id)
        .where(
            ConsultantGrant.organisation_id == organisation_id,
            ConsultantGrant.consultant_user_id == user.id,
            ConsultantGrant.accepted_at.is_not(None),
            ConsultantGrant.revoked_at.is_(None),
            ConsultantGrant.expires_at > datetime.now(UTC),
        )
        .limit(1)
    )
    if grant_org is not None:
        return OrgContext(organisation=grant_org, user=user, role=OrgRole.CONSULTANT)
    return None
