"""The active organisation (chosen with POST /me/active-organisation)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.schemas.organisation import OrganisationOut, OrganisationUpdateIn, organisation_out
from app.services import organisations as organisation_service

router = APIRouter(prefix="/organisation", tags=["organisation"])


@router.get("", response_model=OrganisationOut, status_code=status.HTTP_200_OK)
def get_organisation(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ORGANISATION)),
) -> OrganisationOut:
    return organisation_out(ctx)


@router.patch("", response_model=OrganisationOut, status_code=status.HTTP_200_OK)
def update_organisation(
    body: OrganisationUpdateIn,
    ctx: OrgContext = Depends(require_permission(Permission.EDIT_ORGANISATION)),
    db: Session = Depends(get_db),
) -> OrganisationOut:
    organisation_service.update_profile(
        ctx.organisation, db, actor=ctx.user, changes=body.changes()
    )
    return organisation_out(ctx)
