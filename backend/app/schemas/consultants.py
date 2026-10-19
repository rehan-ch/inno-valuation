import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel

from app.models import ConsultantGrant
from app.models.enums import OrganisationStatus
from app.schemas.common import Email, RequestModel
from app.services.consultant_access import GrantStatus, status_of


def _in_utc(value: datetime) -> datetime:
    try:
        return value.astimezone(UTC)
    except OverflowError as error:  # a date at the very end of year 9999
        raise ValueError("The end date is too far in the future.") from error


# When access ends, chosen by the client, sent with a time zone and stored in UTC. The
# service checks it is in the future and within ``END_DATE_CEILING``.
EndDate = Annotated[AwareDatetime, AfterValidator(_in_utc)]


class ConsultantGrantIn(RequestModel):
    email: Email
    expires_at: EndDate


class ConsultantGrantUpdateIn(RequestModel):
    expires_at: EndDate


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
