"""The signed-in user's own account, and consultant access given to them."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, current_session, current_user, get_db
from app.core.sessions import refresh_session, start_session
from app.models import User
from app.schemas.auth import ChangePasswordIn
from app.schemas.common import MessageOut
from app.schemas.consultants import ConsultantAccessOut, consultant_access_out
from app.schemas.me import ActiveOrganisationIn, MeOut, MeUpdateIn, me_out
from app.services import auth as auth_service
from app.services import consultant_access
from app.services import users as user_service

router = APIRouter(prefix="/me", tags=["me"])


def me_response(db: Session, user: User, active_org_id: uuid.UUID | None) -> MeOut:
    """``MeOut`` for ``user``. ``active_org_id`` is shown only while the user can reach it."""
    return me_out(
        user,
        user_service.list_memberships(db, user),
        user_service.list_consultant_organisations(db, user),
        user_service.active_organisation_id(db, user, active_org_id),
    )


@router.get("", response_model=MeOut, status_code=status.HTTP_200_OK)
def get_me(auth: AuthContext = Depends(current_session), db: Session = Depends(get_db)) -> MeOut:
    return me_response(db, auth.user, auth.claims.active_org_id)


@router.patch("", response_model=MeOut, status_code=status.HTTP_200_OK)
def update_me(
    body: MeUpdateIn,
    auth: AuthContext = Depends(current_session),
    db: Session = Depends(get_db),
) -> MeOut:
    user = user_service.update_name(db, auth.user, name=body.name)
    return me_response(db, user, auth.claims.active_org_id)


@router.post("/active-organisation", response_model=MeOut, status_code=status.HTTP_200_OK)
def set_active_organisation(
    body: ActiveOrganisationIn,
    response: Response,
    auth: AuthContext = Depends(current_session),
    db: Session = Depends(get_db),
) -> MeOut:
    ctx = user_service.choose_active_organisation(
        db, auth.user, organisation_id=body.organisation_id
    )
    claims = refresh_session(response, auth.claims, active_org_id=ctx.organisation_id)
    return me_response(db, auth.user, claims.active_org_id)


@router.post("/password", response_model=MessageOut, status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePasswordIn,
    response: Response,
    auth: AuthContext = Depends(current_session),
    db: Session = Depends(get_db),
) -> MessageOut:
    """Ends every other session; this browser gets a fresh session cookie."""
    auth_service.change_password(
        db,
        auth.user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    start_session(response, auth.user, active_org_id=auth.claims.active_org_id)
    return MessageOut(message="Your password is changed.")


@router.get(
    "/consultant-access",
    response_model=list[ConsultantAccessOut],
    status_code=status.HTTP_200_OK,
)
def list_consultant_access(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ConsultantAccessOut]:
    """Access given to this user's email that has not ended: waiting or active."""
    now = datetime.now(UTC)
    return [consultant_access_out(g, now) for g in consultant_access.for_consultant(db, user)]


@router.post(
    "/consultant-access/{grant_id}/accept",
    response_model=ConsultantAccessOut,
    status_code=status.HTTP_200_OK,
)
def accept_consultant_access(
    grant_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ConsultantAccessOut:
    """Accept access given to this user's email. The organisation then appears in the
    switcher (``consultant_organisations`` on ``/me``)."""
    grant = consultant_access.accept(db, user, grant_id=grant_id)
    return consultant_access_out(grant, datetime.now(UTC))
