"""The active organisation's team: members and invitations. Accepting an invitation is
outside the organisation (the person is not a member yet), under /invitations."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.me import me_response
from app.core.deps import AuthContext, current_session, get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.core.sessions import refresh_session
from app.models import Membership
from app.schemas.common import MessageOut
from app.schemas.me import MeOut
from app.schemas.team import (
    InvitationIn,
    InvitationOut,
    InvitationPreviewOut,
    InvitationTokenIn,
    MemberOut,
    MemberRoleIn,
    invitation_out,
    invitation_preview_out,
)
from app.services import invitations, members

router = APIRouter(prefix="/organisation", tags=["team"])
invitation_router = APIRouter(prefix="/invitations", tags=["team"])


def _member_out(membership: Membership) -> MemberOut:
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        name=membership.user.name,
        email=membership.user.email,
        role=membership.role,
        joined_at=membership.created_at,
    )


# Members


@router.get("/members", response_model=list[MemberOut], status_code=status.HTTP_200_OK)
def list_members(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_TEAM)),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    return [_member_out(m) for m in members.list_members(ctx.organisation, db)]


@router.patch("/members/{membership_id}", response_model=MemberOut, status_code=status.HTTP_200_OK)
def change_member_role(
    membership_id: uuid.UUID,
    body: MemberRoleIn,
    ctx: OrgContext = Depends(require_permission(Permission.CHANGE_ROLES)),
    db: Session = Depends(get_db),
) -> MemberOut:
    membership = members.change_role(
        ctx.organisation, db, ctx=ctx, membership_id=membership_id, role=body.role
    )
    return _member_out(membership)


@router.delete(
    "/members/{membership_id}", response_model=MessageOut, status_code=status.HTTP_200_OK
)
def remove_member(
    membership_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: Session = Depends(get_db),
) -> MessageOut:
    members.remove_member(ctx.organisation, db, ctx=ctx, membership_id=membership_id)
    return MessageOut(message="The member is removed.")


# Invitations (the inviting side)


@router.get("/invitations", response_model=list[InvitationOut], status_code=status.HTTP_200_OK)
def list_invitations(
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: Session = Depends(get_db),
) -> list[InvitationOut]:
    now = datetime.now(UTC)
    return [invitation_out(p, now) for p in invitations.list_pending(ctx.organisation, db)]


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def invite(
    body: InvitationIn,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: Session = Depends(get_db),
) -> InvitationOut:
    """Invite someone by email. Inviting the same email again replaces the old link."""
    invitation = invitations.invite(ctx.organisation, db, ctx=ctx, email=body.email, role=body.role)
    pending = invitations.PendingInvitation(invitation=invitation, invited_by_name=ctx.user.name)
    return invitation_out(pending, datetime.now(UTC))


@router.delete(
    "/invitations/{invitation_id}", response_model=MessageOut, status_code=status.HTTP_200_OK
)
def revoke_invitation(
    invitation_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: Session = Depends(get_db),
) -> MessageOut:
    invitations.revoke(ctx.organisation, db, ctx=ctx, invitation_id=invitation_id)
    return MessageOut(message="The invitation is cancelled.")


# Invitations (the invited side)


@invitation_router.post(
    "/preview", response_model=InvitationPreviewOut, status_code=status.HTTP_200_OK
)
def preview_invitation(
    body: InvitationTokenIn, db: Session = Depends(get_db)
) -> InvitationPreviewOut:
    """What the invitation is for. No session needed: the token is the proof."""
    return invitation_preview_out(invitations.preview(db, token=body.token))


@invitation_router.post("/accept", response_model=MeOut, status_code=status.HTTP_200_OK)
def accept_invitation(
    body: InvitationTokenIn,
    response: Response,
    auth: AuthContext = Depends(current_session),
    db: Session = Depends(get_db),
) -> MeOut:
    """Join the organisation, signed in with the invited email. It becomes the active one."""
    org = invitations.accept(db, auth.user, token=body.token)
    claims = refresh_session(response, auth.claims, active_org_id=org.id)
    return me_response(db, auth.user, claims.active_org_id)
