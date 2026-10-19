"""Sign-in protection that is not tied to a user row.

``SignInThrottle`` counts password attempts per email address, whether or not an account
exists for it, so a lock never reveals which emails are registered. An attempt is counted
before the password is checked, under a row lock, so parallel guesses cannot pass the limit.
The key is an HMAC of the normalised email (keyed with the app secret), so the table holds
no email.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import Timestamps, UuidPrimaryKey

THROTTLE_KEY_LENGTH = 64  # HMAC-SHA256 hex digest.


class SignInThrottle(UuidPrimaryKey, Timestamps, Base):
    __tablename__ = "sign_in_throttles"
    __table_args__ = (CheckConstraint("attempt_count >= 0", name="attempt_count_not_negative"),)

    key_hash: Mapped[str] = mapped_column(String(THROTTLE_KEY_LENGTH), unique=True)
    # Attempts since the last successful sign-in, inside the current window.
    attempt_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # Start of the current counting window. Attempts older than the window are forgotten.
    window_started_at: Mapped[datetime | None]
    locked_until: Mapped[datetime | None]
