"""New-password policy, NIST SP 800-63B style.

Length is enforced by the request schemas (10 to 128 characters). There are no
composition rules on purpose: NIST advises against them. What this module adds
is the other half of the guidance: a new password must not be a known
commonly-used password, and must not contain obvious context words (the
holder's email or name, or the product name).

`common_passwords.txt` is the UK NCSC "100k most used passwords" list (from
the Have I Been Pwned corpus, via SecLists), filtered to the entries that pass
the length rule, lower-cased and de-duplicated. A live Have I Been Pwned
range check can replace the static list when the app goes live (Phase 8).
"""

from functools import lru_cache
from pathlib import Path
from typing import Final

from app.core.errors import AppError

_LIST_PATH: Final = Path(__file__).with_name("common_passwords.txt")

# A context word this short would reject too many honest passphrases.
_MIN_CONTEXT_LENGTH: Final = 4

PRODUCT_NAME: Final = "innovaluation"


@lru_cache(maxsize=1)
def common_passwords() -> frozenset[str]:
    with _LIST_PATH.open(encoding="utf-8") as handle:
        return frozenset(line.strip().lower() for line in handle if line.strip())


def _weak(message: str) -> AppError:
    return AppError("weak_password", message, 422)


def check_new_password(password: str, *, email: str, name: str | None = None) -> None:
    """Raise 422 ``weak_password`` when the password is guessable.

    Call it wherever a password is set: sign-up, the choose-a-password
    verification link, password reset and password change.
    """
    lowered = password.lower()
    if lowered in common_passwords():
        raise _weak(
            "This password appears on the list of commonly used passwords. "
            "Pick something more unusual; a few random words work well."
        )
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= _MIN_CONTEXT_LENGTH and local_part in lowered:
        raise _weak("The password must not contain your email address.")
    for part in (name or "").split():
        if len(part) >= _MIN_CONTEXT_LENGTH and part.lower() in lowered:
            raise _weak("The password must not contain your name.")
    if PRODUCT_NAME in lowered:
        raise _weak("The password must not contain the product name.")
