import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import MembershipRole
from app.schemas.auth import Token
from app.schemas.common import Email, RequestModel
from app.services.invitations import InvitationPreview, PendingInvitation


class MemberOut(BaseModel):
    id: uuid.UUID  # the membership id, used to change the role or remove the member
    user_id: uuid.UUID
    name: str
    email: str
    role: MembershipRole
    joined_at: datetime


class MemberRoleIn(RequestModel):
    role: MembershipRole


class InvitationIn(RequestModel):
    email: Email
    role: MembershipRole


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: MembershipRole
    invited_by_name: str | None
    created_at: datetime
    expires_at: datetime
    expired: bool


def invitation_out(pending: PendingInvitation, now: datetime) -> InvitationOut:
    inv = pending.invitation
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=inv.role,
        invited_by_name=pending.invited_by_name,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        expired=inv.expires_at <= now,
    )


class InvitationTokenIn(RequestModel):
    token: Token


class InvitationPreviewOut(BaseModel):
    organisation_name: str
    # The invited address, so the page can say which account to sign in with.
    email: str
    role: MembershipRole
    expires_at: datetime


def invitation_preview_out(preview: InvitationPreview) -> InvitationPreviewOut:
    return InvitationPreviewOut(
        organisation_name=preview.organisation_name,
        email=preview.email,
        role=preview.role,
        expires_at=preview.expires_at,
    )
