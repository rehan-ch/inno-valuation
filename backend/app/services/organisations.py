"""The active organisation's profile. Organisation creation and members arrive with the
members work; this module only reads and edits the profile."""

from typing import Any, Final

from sqlalchemy.orm import Session

from app.models import Organisation, User
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
