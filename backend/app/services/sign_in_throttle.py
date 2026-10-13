"""Limit password attempts per email, in Postgres (no Redis needed).

Every email is counted the same way whether or not an account exists, so a lock never
reveals which emails are registered.

The order matters (``begin_attempt`` before the password check, ``attempt_failed`` or
``clear`` after):
1. ``begin_attempt`` counts the attempt under ``SELECT ... FOR UPDATE`` and refuses it when
   the email is locked or the window already holds ``MAX_ATTEMPTS`` attempts. The caller
   commits at once, releasing the row lock before the slow password check. Parallel
   requests therefore queue on the row lock and at most ``MAX_ATTEMPTS`` pass per window.
2. On a wrong password, ``attempt_failed`` locks the email for ``LOCK_DURATION`` once the
   window holds ``MAX_ATTEMPTS`` attempts.
3. On success, ``clear`` deletes the row.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.security import throttle_key
from app.models import SignInThrottle

MAX_ATTEMPTS: Final = 5
WINDOW: Final = timedelta(minutes=15)
LOCK_DURATION: Final = timedelta(minutes=15)


@dataclass(frozen=True)
class Attempt:
    allowed: bool
    # True only for the request that set a new lock, so the lock is audited once.
    newly_locked: bool = False


def begin_attempt(db: Session, normalised_email: str, now: datetime | None = None) -> Attempt:
    """Count one attempt, or refuse it. The caller commits straight after."""
    now = now or datetime.now(UTC)
    row = _locked_row(db, normalised_email)
    if row.locked_until is not None and row.locked_until > now:
        return Attempt(allowed=False)
    lock_over = row.locked_until is not None
    window_over = row.window_started_at is None or row.window_started_at <= now - WINDOW
    if lock_over or window_over:
        row.attempt_count = 0
        row.locked_until = None
        row.window_started_at = now
    if row.attempt_count >= MAX_ATTEMPTS:
        # The window is full of attempts still being checked: lock now.
        row.locked_until = now + LOCK_DURATION
        db.flush()
        return Attempt(allowed=False, newly_locked=True)
    row.attempt_count += 1
    db.flush()
    return Attempt(allowed=True)


def attempt_failed(db: Session, normalised_email: str, now: datetime | None = None) -> bool:
    """Record that the counted attempt was wrong. True if this set a new lock. Caller commits."""
    now = now or datetime.now(UTC)
    row = _locked_row(db, normalised_email)
    if row.locked_until is not None and row.locked_until > now:
        return False
    if row.attempt_count >= MAX_ATTEMPTS:
        row.locked_until = now + LOCK_DURATION
        db.flush()
        return True
    return False


def is_locked(db: Session, normalised_email: str, now: datetime | None = None) -> bool:
    row = db.scalar(
        select(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(normalised_email))
    )
    now = now or datetime.now(UTC)
    return row is not None and row.locked_until is not None and row.locked_until > now


def clear(db: Session, normalised_email: str) -> None:
    """Forget attempts after a successful sign-in or password reset. Caller commits."""
    db.execute(
        delete(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(normalised_email))
    )


def _locked_row(db: Session, normalised_email: str) -> SignInThrottle:
    key = throttle_key(normalised_email)
    # Create the row if missing, then lock it, so concurrent requests count one by one.
    db.execute(insert(SignInThrottle).values(key_hash=key).on_conflict_do_nothing())
    return db.scalars(
        select(SignInThrottle)
        .where(SignInThrottle.key_hash == key)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
