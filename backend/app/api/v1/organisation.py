"""Organisations: create one, and read or edit the active one (chosen with
POST /me/active-organisation)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, current_session, get_db, require_permission
from app.core.permissions import OrgContext, OrgRole, Permission
from app.core.sessions import refresh_session
from app.schemas.organisation import (
    OrganisationCreateIn,
    OrganisationOut,
    OrganisationUpdateIn,
    organisation_out,
)
from app.services import organisations as organisation_service

router = APIRouter(prefix="/organisation", tags=["organisation"])
create_router = APIRouter(prefix="/organisations", tags=["organisation"])


@create_router.post("", response_model=OrganisationOut, status_code=status.HTTP_201_CREATED)
def create_organisation(
    body: OrganisationCreateIn,
    response: Response,
    auth: AuthContext = Depends(current_session),
    db: Session = Depends(get_db),
) -> OrganisationOut:
    """Any signed-in user may create an organisation. They become its owner, and it becomes
    their active organisation."""
    org = organisation_service.create_organisation(db, creator=auth.user, values=body.values())
    refresh_session(response, auth.claims, active_org_id=org.id)
    return organisation_out(OrgContext(organisation=org, user=auth.user, role=OrgRole.OWNER))


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
