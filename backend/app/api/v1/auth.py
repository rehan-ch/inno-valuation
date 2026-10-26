"""Email and password sign-in. Routes without a session are protected from other sites by
the router-wide origin check; routes with a session also need the CSRF header."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.me import me_response
from app.core.deps import AuthContext, get_db, session_if_csrf_valid
from app.core.sessions import clear_session, start_session
from app.schemas.auth import EmailIn, ResetPasswordIn, SignInIn, SignUpIn, VerifyEmailIn
from app.schemas.common import MessageOut
from app.schemas.me import MeOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

CHECK_INBOX = "If this email can be used, we have sent a message to it. Check your inbox."


def limit_by_address(request: Request, db: Session = Depends(get_db)) -> None:
    """The per-address limit on the routes that check a password or send an email to any
    address given (see ``sign_in_throttle``). 429 ``too_many_attempts`` when exceeded."""
    auth_service.check_address_limit(db, request.client.host if request.client else None)


@router.post("/sign-up", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def sign_up(body: SignUpIn, db: Session = Depends(get_db)) -> MessageOut:
    auth_service.sign_up(db, email=body.email, name=body.name, password=body.password)
    return MessageOut(message=CHECK_INBOX)


@router.post("/verify-email", response_model=MessageOut, status_code=status.HTTP_200_OK)
def verify_email(body: VerifyEmailIn, db: Session = Depends(get_db)) -> MessageOut:
    auth_service.verify_email(db, token=body.token, password=body.password)
    return MessageOut(message="Your email is confirmed. You can sign in now.")


@router.post(
    "/verify-email/resend",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_by_address)],
)
def resend_verification(body: EmailIn, db: Session = Depends(get_db)) -> MessageOut:
    auth_service.resend_verification(db, email=body.email)
    return MessageOut(message=CHECK_INBOX)


@router.post(
    "/sign-in",
    response_model=MeOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(limit_by_address)],
)
def sign_in(body: SignInIn, response: Response, db: Session = Depends(get_db)) -> MeOut:
    result = auth_service.sign_in(db, email=body.email, password=body.password)
    claims = start_session(response, result.user, active_org_id=result.active_org_id)
    return me_response(db, result.user, claims.active_org_id)


@router.post("/sign-out", response_model=MessageOut, status_code=status.HTTP_200_OK)
def sign_out(
    response: Response,
    auth: AuthContext | None = Depends(session_if_csrf_valid),
    db: Session = Depends(get_db),
) -> MessageOut:
    """Ends the session in this browser, on the server too. Always clears the cookies; the
    session is revoked and audited only with a valid session and a passing CSRF check."""
    if auth is not None:
        auth_service.sign_out(db, auth.user, auth.claims)
    clear_session(response)
    return MessageOut(message="You are signed out.")


@router.post(
    "/password/forgot",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_by_address)],
)
def forgot_password(body: EmailIn, db: Session = Depends(get_db)) -> MessageOut:
    auth_service.request_password_reset(db, email=body.email)
    return MessageOut(message=CHECK_INBOX)


@router.post("/password/reset", response_model=MessageOut, status_code=status.HTTP_200_OK)
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)) -> MessageOut:
    auth_service.reset_password(db, token=body.token, new_password=body.new_password)
    return MessageOut(message="Your password is changed. Sign in with the new password.")
