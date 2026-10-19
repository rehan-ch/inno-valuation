"""Organisations: create one, edit the active organisation's profile.

Team changes (members, invitations, consultant access) lock the organisation row first with
``lock_organisation``, so two admins acting at once cannot, for example, both demote the
other and leave the organisation without an owner.
"""

import math
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Membership, Organisation, User
from app.models.enums import MembershipRole
from app.services.audit import AuditAction, record

EDITABLE_FIELDS: Final = frozenset(
    {
        "name",
        "description",
        "industry",
        "country",
        "size_band",
        "revenue_band",
        "founder_names",
        "website",
        "primary_contact_name",
        "primary_contact_email",
        "currency",
    }
)

# Abuse limit, not a product rule: a new organisation can send invitations, so one account
# cannot create organisations without limit.
CREATE_LIMIT: Final = 10
CREATE_LIMIT_PERIOD: Final = timedelta(days=1)


_MINUTES_PER_HOUR: Final = 60


def describe_wait(delta: timedelta) -> str:
    """'in 7 minutes', 'in about 3 hours': rounded up, so the person never retries early."""
    minutes = max(1, math.ceil(delta.total_seconds() / 60))
    if minutes < _MINUTES_PER_HOUR:
        return "in 1 minute" if minutes == 1 else f"in {minutes} minutes"
    hours = math.ceil(minutes / _MINUTES_PER_HOUR)
    return "in about 1 hour" if hours == 1 else f"in about {hours} hours"


def too_many_requests(rule: str, retry_in: timedelta) -> AppError:
    """A refused abuse limit, saying which rule and when the next request is allowed.

    ``rule`` is a full sentence; ``retry_in`` is when the oldest counted request leaves
    the rolling window.
    """
    return AppError("too_many_requests", f"{rule} Try again {describe_wait(retry_in)}.", 429)


def oldest_in_window(db: Session, stmt: Select[datetime]) -> datetime:
    """The oldest timestamp a limit query counted (``stmt`` selects ``min(created_at)``)."""
    oldest: datetime | None = db.scalar(stmt)
    return oldest if oldest is not None else datetime.now(UTC)


def lock_organisation(db: Session, org: Organisation) -> None:
    """Lock the organisation row until the transaction ends. Every team change takes it."""
    db.execute(select(Organisation.id).where(Organisation.id == org.id).with_for_update())


def create_organisation(db: Session, *, creator: User, values: dict[str, Any]) -> Organisation:
    """Create an organisation with ``creator`` as its owner. Commits."""
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Not settable: {sorted(unknown)}")
    now = datetime.now(UTC)
    in_window = (
        Organisation.created_by_user_id == creator.id,
        Organisation.created_at > now - CREATE_LIMIT_PERIOD,
    )
    recent = db.scalar(select(func.count()).select_from(Organisation).where(*in_window))
    if (recent or 0) >= CREATE_LIMIT:
        oldest = oldest_in_window(db, select(func.min(Organisation.created_at)).where(*in_window))
        raise too_many_requests(
            f"You have created {CREATE_LIMIT} organisations in the last day, the most allowed.",
            oldest + CREATE_LIMIT_PERIOD - now,
        )
    org = Organisation(created_by_user_id=creator.id, **values)
    db.add(org)
    db.flush()
    db.add(Membership(organisation_id=org.id, user_id=creator.id, role=MembershipRole.OWNER))
    record(
        db,
        AuditAction.ORGANISATION_CREATED,
        actor=creator,
        organisation_id=org.id,
        target_type="organisation",
        target_id=org.id,
    )
    db.commit()
    return org


def update_profile(
    org: Organisation, db: Session, *, actor: User, changes: dict[str, Any]
) -> Organisation:
    """Apply profile changes. The audit event lists changed field names only, never values."""
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Not editable: {sorted(unknown)}")
    changed = sorted(field for field, value in changes.items() if getattr(org, field) != value)
    for field in changed:
        setattr(org, field, changes[field])
    if changed:
        record(
            db,
            AuditAction.ORGANISATION_UPDATED,
            actor=actor,
            organisation_id=org.id,
            target_type="organisation",
            target_id=org.id,
            details={"fields": changed},
        )
    db.commit()
    return org
