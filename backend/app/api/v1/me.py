"""The signed-in user's own account."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, current_session, get_db
from app.core.sessions import refresh_session, start_session
from app.schemas.auth import ChangePasswordIn
from app.schemas.common import MessageOut
from app.schemas.me import ActiveOrganisationIn, MeOut, MeUpdateIn, me_out
from app.services import auth as auth_service
from app.services import users as user_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut, status_code=status.HTTP_200_OK)
def get_me(auth: AuthContext = Depends(current_session), db: Session = Depends(get_db)) -> MeOut:
    memberships = user_service.list_memberships(db, auth.user)
    return me_out(auth.user, memberships, auth.claims.active_org_id)


@router.patch("", response_model=MeOut, status_code=status.HTTP_200_OK)
def update_me(
    body: MeUpdateIn,
    auth: AuthContext = Depends(current_session),
    db: Session = Depends(get_db),
) -> MeOut:
    user = user_service.update_name(db, auth.user, name=body.name)
    return me_out(user, user_service.list_memberships(db, user), auth.claims.active_org_id)


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
    return me_out(auth.user, user_service.list_memberships(db, auth.user), claims.active_org_id)


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
