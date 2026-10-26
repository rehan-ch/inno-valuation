"""Shared request field types and response models."""

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.core.security import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.models.accounts import EMAIL_LENGTH

Email = Annotated[EmailStr, Field(max_length=EMAIL_LENGTH)]
# Passwords are never trimmed: spaces count.
NewPassword = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
# Existing passwords are checked against the hash, so only the upper bound applies.
AnyPassword = Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def no_control_characters(value: str) -> str:
    """Refuse line breaks and other control characters. Names go into plain-text emails,
    where a line break would let one user add lines of their own to the message."""
    if _CONTROL_CHARACTERS.search(value):
        raise ValueError("must not contain line breaks or other control characters")
    return value


NoControlCharacters = AfterValidator(no_control_characters)
PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    NoControlCharacters,
]


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class MessageOut(BaseModel):
    message: str
