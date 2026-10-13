import uuid

from pydantic import BaseModel

from app.models import Membership, User
from app.models.enums import MembershipRole
from app.schemas.common import PersonName, RequestModel


class MembershipOut(BaseModel):
    organisation_id: uuid.UUID
    organisation_name: str
    role: MembershipRole


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    email_verified: bool
    active_organisation_id: uuid.UUID | None
    memberships: list[MembershipOut]


class MeUpdateIn(RequestModel):
    name: PersonName


class ActiveOrganisationIn(RequestModel):
    organisation_id: uuid.UUID


def me_out(
    user: User, memberships: list[Membership], active_organisation_id: uuid.UUID | None
) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        email_verified=user.email_verified_at is not None,
        active_organisation_id=active_organisation_id,
        memberships=[
            MembershipOut(
                organisation_id=m.organisation_id,
                organisation_name=m.organisation.name,
                role=m.role,
            )
            for m in memberships
        ],
    )
