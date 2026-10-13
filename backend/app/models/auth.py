"""Sign-in protection that is not tied to a user row.

``SignInThrottle`` counts failed password sign-ins per email address, whether or not an
account exists for it, so a lock never reveals which emails are registered. The key is an
HMAC of the normalised email (keyed with the app secret), so the table holds no email.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import Timestamps, UuidPrimaryKey

THROTTLE_KEY_LENGTH = 64  # HMAC-SHA256 hex digest.


class SignInThrottle(UuidPrimaryKey, Timestamps, Base):
    __tablename__ = "sign_in_throttles"
    __table_args__ = (CheckConstraint("failed_count >= 0", name="failed_count_not_negative"),)

    key_hash: Mapped[str] = mapped_column(String(THROTTLE_KEY_LENGTH), unique=True)
    failed_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # Start of the current counting window. Failures older than the window are forgotten.
    first_failed_at: Mapped[datetime | None]
    locked_until: Mapped[datetime | None]
