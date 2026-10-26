"""Sign-in protection that is not tied to a user row, and sessions ended early.

``SignInThrottle`` counts password attempts per email address, whether or not an account
exists for it, so a lock never reveals which emails are registered. An attempt is counted
before the password is checked, under a row lock, so parallel guesses cannot pass the limit.
The key is an HMAC of the normalised email (keyed with the app secret), so the table holds
no email. The same table counts requests per client address under a separate key.

``RevokedSession`` holds the id of every session ended by sign-out before its own expiry.
A row is useless once the session would have expired anyway, so expired rows are purged.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, Timestamps, UuidPrimaryKey

THROTTLE_KEY_LENGTH = 64  # HMAC-SHA256 hex digest.
SESSION_ID_LENGTH = 64  # ``new_session_id`` gives 22 characters; room for a longer form.


class SignInThrottle(UuidPrimaryKey, Timestamps, Base):
    __tablename__ = "sign_in_throttles"
    __table_args__ = (CheckConstraint("attempt_count >= 0", name="attempt_count_not_negative"),)

    key_hash: Mapped[str] = mapped_column(String(THROTTLE_KEY_LENGTH), unique=True)
    # Attempts since the last successful sign-in, inside the current window.
    attempt_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # Start of the current counting window. Attempts older than the window are forgotten.
    window_started_at: Mapped[datetime | None]
    locked_until: Mapped[datetime | None]


class RevokedSession(UuidPrimaryKey, CreatedAt, Base):
    __tablename__ = "revoked_sessions"

    sid: Mapped[str] = mapped_column(String(SESSION_ID_LENGTH), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # When the session itself expires; the row is not needed after that.
    expires_at: Mapped[datetime]
