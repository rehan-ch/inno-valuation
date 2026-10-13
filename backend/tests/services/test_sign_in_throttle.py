from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import throttle_key
from app.models import SignInThrottle
from app.services import sign_in_throttle as throttle
from tests.factories import SignInThrottleFactory

EMAIL = "person@example.com"


def _row(db: Session) -> SignInThrottle:
    return db.scalars(
        select(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(EMAIL))
    ).one()


def test_locks_after_max_failures(db: Session) -> None:
    now = datetime.now(UTC)
    results = [throttle.record_failure(db, EMAIL, now) for _ in range(throttle.MAX_FAILURES)]
    assert results == [False] * (throttle.MAX_FAILURES - 1) + [True]
    assert throttle.is_locked(db, EMAIL, now)
    assert not throttle.is_locked(db, EMAIL, now + throttle.LOCK_DURATION + timedelta(seconds=1))
    assert not throttle.is_locked(db, "other@example.com", now)


def test_failures_outside_the_window_are_forgotten(db: Session) -> None:
    start = datetime.now(UTC)
    for _ in range(throttle.MAX_FAILURES - 1):
        throttle.record_failure(db, EMAIL, start)
    later = start + throttle.WINDOW + timedelta(seconds=1)
    assert throttle.record_failure(db, EMAIL, later) is False
    assert _row(db).failed_count == 1


def test_counting_restarts_after_a_lock_ends(db: Session) -> None:
    now = datetime.now(UTC)
    for _ in range(throttle.MAX_FAILURES):
        throttle.record_failure(db, EMAIL, now)
    after = now + throttle.LOCK_DURATION + timedelta(seconds=1)
    assert throttle.record_failure(db, EMAIL, after) is False
    row = _row(db)
    assert row.failed_count == 1
    assert row.locked_until is None


def test_clear_removes_the_row(db: Session) -> None:
    throttle.record_failure(db, EMAIL)
    throttle.clear(db, EMAIL)
    assert db.scalars(select(SignInThrottle)).all() == []


def test_factory_row_is_not_locked(db: Session) -> None:
    row = SignInThrottleFactory.create()
    assert row.locked_until is None
