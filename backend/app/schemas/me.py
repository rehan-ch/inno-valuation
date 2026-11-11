import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.settings import get_settings
from app.models import ConsultantGrant, Membership, User
from app.models.enums import MembershipRole, OrganisationStatus
from app.schemas.common import PersonName, RequestModel


class MembershipOut(BaseModel):
    organisation_id: uuid.UUID
    organisation_name: str
    # An archived organisation is view-only and cannot be chosen as the active one.
    organisation_status: OrganisationStatus
    role: MembershipRole


class ConsultantOrganisationOut(BaseModel):
    """An organisation the user sees as a consultant, through accepted, live access."""

    organisation_id: uuid.UUID
    organisation_name: str
    organisation_status: OrganisationStatus
    access_ends_at: datetime


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    email_verified: bool
    active_organisation_id: uuid.UUID | None
    memberships: list[MembershipOut]
    # For the organisation switcher, next to the memberships. Read-only access.
    consultant_organisations: list[ConsultantOrganisationOut]
    # False while the server has no AI key. The app then hides what needs the AI: the
    # question explanations and everything about ideas and the IQ.
    ai_enabled: bool


class MeUpdateIn(RequestModel):
    name: PersonName


class ActiveOrganisationIn(RequestModel):
    organisation_id: uuid.UUID


def me_out(
    user: User,
    memberships: list[Membership],
    consultant_grants: list[ConsultantGrant],
    active_organisation_id: uuid.UUID | None,
) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        email_verified=user.email_verified_at is not None,
        active_organisation_id=active_organisation_id,
        ai_enabled=bool(get_settings().anthropic_api_key),
        memberships=[
            MembershipOut(
                organisation_id=m.organisation_id,
                organisation_name=m.organisation.name,
                organisation_status=m.organisation.status,
                role=m.role,
            )
            for m in memberships
        ],
        consultant_organisations=[
            ConsultantOrganisationOut(
                organisation_id=g.organisation_id,
                organisation_name=g.organisation.name,
                organisation_status=g.organisation.status,
                access_ends_at=g.expires_at,
            )
            for g in consultant_grants
        ],
    )
