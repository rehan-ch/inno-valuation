from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import AnyPassword, Email, NewPassword, PersonName, RequestModel

# A raw email token is 43 characters (base64url of 32 bytes); allow some slack.
Token = Annotated[str, Field(min_length=1, max_length=200)]


class SignUpIn(RequestModel):
    email: Email
    name: PersonName
    password: NewPassword
    accepted_terms: Literal[True]


class SignInIn(RequestModel):
    email: Email
    password: AnyPassword


class EmailIn(RequestModel):
    email: Email


class VerifyEmailIn(RequestModel):
    token: Token
    # Needed only when the link requires a password (the API answers 400
    # ``password_required``); ignored otherwise.
    password: NewPassword | None = None


class ResetPasswordIn(RequestModel):
    token: Token
    new_password: NewPassword


class ChangePasswordIn(RequestModel):
    current_password: AnyPassword
    new_password: NewPassword
