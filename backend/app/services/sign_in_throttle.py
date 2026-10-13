"""Limit repeated failed password sign-ins, per email, in Postgres (no Redis needed).

Every email is counted the same way whether or not an account exists, so a lock never
reveals which emails are registered. After ``MAX_FAILURES`` failures inside ``WINDOW`` the
email is locked for ``LOCK_DURATION``; while locked, even the right password is refused.
"""

from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.security import throttle_key
from app.models import SignInThrottle

MAX_FAILURES: Final = 5
WINDOW: Final = timedelta(minutes=15)
LOCK_DURATION: Final = timedelta(minutes=15)


def is_locked(db: Session, normalised_email: str, now: datetime | None = None) -> bool:
    row = db.scalar(
        select(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(normalised_email))
    )
    return _locked(row, now or datetime.now(UTC))


def record_failure(db: Session, normalised_email: str, now: datetime | None = None) -> bool:
    """Count one failure. Returns True if the email is now locked. Caller commits."""
    now = now or datetime.now(UTC)
    key = throttle_key(normalised_email)
    # Create the row if missing, then lock it, so concurrent failures count correctly.
    db.execute(insert(SignInThrottle).values(key_hash=key).on_conflict_do_nothing())
    row = db.scalars(
        select(SignInThrottle)
        .where(SignInThrottle.key_hash == key)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    lock_over = row.locked_until is not None and row.locked_until <= now
    window_over = row.first_failed_at is None or row.first_failed_at <= now - WINDOW
    if lock_over or window_over:
        row.failed_count = 0
        row.locked_until = None
    if row.failed_count == 0:
        row.first_failed_at = now
    row.failed_count += 1
    if row.failed_count >= MAX_FAILURES:
        row.locked_until = now + LOCK_DURATION
    db.flush()
    return _locked(row, now)


def clear(db: Session, normalised_email: str) -> None:
    """Forget failures after a successful sign-in or password reset. Caller commits."""
    db.execute(
        delete(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(normalised_email))
    )


def _locked(row: SignInThrottle | None, now: datetime) -> bool:
    return row is not None and row.locked_until is not None and row.locked_until > now
