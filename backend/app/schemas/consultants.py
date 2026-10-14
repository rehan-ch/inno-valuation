import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel

from app.models import ConsultantGrant
from app.models.enums import OrganisationStatus
from app.schemas.common import Email, RequestModel
from app.services.consultant_access import GrantStatus, status_of


class ConsultantGrantIn(RequestModel):
    email: Email
    # When access ends, chosen by the client. Must be in the future; sent with a time zone.
    expires_at: AwareDatetime


class ConsultantGrantUpdateIn(RequestModel):
    expires_at: AwareDatetime


class ConsultantGrantOut(BaseModel):
    """A grant as the client's admin sees it."""

    id: uuid.UUID
    email: str
    status: GrantStatus
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


def consultant_grant_out(grant: ConsultantGrant, now: datetime) -> ConsultantGrantOut:
    return ConsultantGrantOut(
        id=grant.id,
        email=grant.consultant_email,
        status=status_of(grant, now),
        expires_at=grant.expires_at,
        created_at=grant.created_at,
        accepted_at=grant.accepted_at,
        revoked_at=grant.revoked_at,
    )


class ConsultantAccessOut(BaseModel):
    """Access as the consultant sees it: waiting for them to accept, or active."""

    id: uuid.UUID
    organisation_id: uuid.UUID
    organisation_name: str
    organisation_status: OrganisationStatus
    status: GrantStatus
    expires_at: datetime


def consultant_access_out(grant: ConsultantGrant, now: datetime) -> ConsultantAccessOut:
    return ConsultantAccessOut(
        id=grant.id,
        organisation_id=grant.organisation_id,
        organisation_name=grant.organisation.name,
        organisation_status=grant.organisation.status,
        status=status_of(grant, now),
        expires_at=grant.expires_at,
    )
