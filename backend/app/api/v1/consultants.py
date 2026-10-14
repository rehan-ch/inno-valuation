"""Consultant access to the active organisation, managed by its owners and admins. The
consultant's own side (list and accept) is under /me/consultant-access."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.schemas.consultants import (
    ConsultantGrantIn,
    ConsultantGrantOut,
    ConsultantGrantUpdateIn,
    consultant_grant_out,
)
from app.services import consultant_access

router = APIRouter(prefix="/organisation/consultants", tags=["consultants"])

_manage = require_permission(Permission.MANAGE_CONSULTANT_ACCESS)


@router.get("", response_model=list[ConsultantGrantOut], status_code=status.HTTP_200_OK)
def list_grants(
    ctx: OrgContext = Depends(_manage), db: Session = Depends(get_db)
) -> list[ConsultantGrantOut]:
    now = datetime.now(UTC)
    return [
        consultant_grant_out(g, now) for g in consultant_access.list_grants(ctx.organisation, db)
    ]


@router.post("", response_model=ConsultantGrantOut, status_code=status.HTTP_201_CREATED)
def grant_access(
    body: ConsultantGrantIn, ctx: OrgContext = Depends(_manage), db: Session = Depends(get_db)
) -> ConsultantGrantOut:
    """Give a consultant read-only access until the chosen end date, and email them."""
    grant = consultant_access.grant(
        ctx.organisation, db, ctx=ctx, email=body.email, expires_at=body.expires_at
    )
    return consultant_grant_out(grant, datetime.now(UTC))


@router.patch("/{grant_id}", response_model=ConsultantGrantOut, status_code=status.HTTP_200_OK)
def change_end_date(
    grant_id: uuid.UUID,
    body: ConsultantGrantUpdateIn,
    ctx: OrgContext = Depends(_manage),
    db: Session = Depends(get_db),
) -> ConsultantGrantOut:
    grant = consultant_access.change_end_date(
        ctx.organisation, db, ctx=ctx, grant_id=grant_id, expires_at=body.expires_at
    )
    return consultant_grant_out(grant, datetime.now(UTC))


@router.delete("/{grant_id}", response_model=ConsultantGrantOut, status_code=status.HTTP_200_OK)
def revoke_access(
    grant_id: uuid.UUID, ctx: OrgContext = Depends(_manage), db: Session = Depends(get_db)
) -> ConsultantGrantOut:
    """End access now."""
    grant = consultant_access.revoke(ctx.organisation, db, ctx=ctx, grant_id=grant_id)
    return consultant_grant_out(grant, datetime.now(UTC))
