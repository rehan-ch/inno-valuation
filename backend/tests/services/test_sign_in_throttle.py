"""The sign-in throttle counts attempts before the password is checked."""

import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.security import throttle_key
from app.models import SignInThrottle
from app.services import sign_in_throttle as throttle
from tests.factories import SignInThrottleFactory

EMAIL = "person@example.com"


def _row(db: Session, email: str = EMAIL) -> SignInThrottle:
    return db.scalars(
        select(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(email))
    ).one()


def _fail(db: Session, now: datetime) -> tuple[bool, bool]:
    """One wrong-password attempt: (allowed, locked afterwards)."""
    attempt = throttle.begin_attempt(db, EMAIL, now)
    if not attempt.allowed:
        return False, True
    return True, throttle.attempt_failed(db, EMAIL, now)


def test_locks_after_max_attempts(db: Session) -> None:
    now = datetime.now(UTC)
    results = [_fail(db, now) for _ in range(throttle.MAX_ATTEMPTS)]
    assert results == [(True, False)] * (throttle.MAX_ATTEMPTS - 1) + [(True, True)]
    assert throttle.is_locked(db, EMAIL, now)
    refused = throttle.begin_attempt(db, EMAIL, now)
    assert not refused.allowed
    assert not refused.newly_locked  # the lock was already announced
    assert not throttle.is_locked(db, EMAIL, now + throttle.LOCK_DURATION + timedelta(seconds=1))
    assert not throttle.is_locked(db, "other@example.com", now)


def test_attempts_are_counted_before_the_check(db: Session) -> None:
    """Attempts still being checked fill the window: the next one is refused and locks."""
    now = datetime.now(UTC)
    for _ in range(throttle.MAX_ATTEMPTS):
        assert throttle.begin_attempt(db, EMAIL, now).allowed
    over = throttle.begin_attempt(db, EMAIL, now)
    assert not over.allowed
    assert over.newly_locked


def test_attempts_outside_the_window_are_forgotten(db: Session) -> None:
    start = datetime.now(UTC)
    for _ in range(throttle.MAX_ATTEMPTS - 1):
        _fail(db, start)
    later = start + throttle.WINDOW + timedelta(seconds=1)
    assert _fail(db, later) == (True, False)
    assert _row(db).attempt_count == 1


def test_counting_restarts_after_a_lock_ends(db: Session) -> None:
    now = datetime.now(UTC)
    for _ in range(throttle.MAX_ATTEMPTS):
        _fail(db, now)
    after = now + throttle.LOCK_DURATION + timedelta(seconds=1)
    assert _fail(db, after) == (True, False)
    row = _row(db)
    assert row.attempt_count == 1
    assert row.locked_until is None


def test_clear_removes_the_row(db: Session) -> None:
    throttle.begin_attempt(db, EMAIL)
    throttle.clear(db, EMAIL)
    assert db.scalars(select(SignInThrottle)).all() == []


def test_factory_row_is_not_locked(db: Session) -> None:
    row = SignInThrottleFactory.create()
    assert row.locked_until is None


# Concurrency: real transactions on separate connections, outside the test rollback.


@pytest.fixture
def race_email(db_engine: Engine) -> Iterator[str]:
    email = f"race-{uuid.uuid4().hex}@example.com"
    yield email
    with Session(db_engine) as session:
        session.execute(
            delete(SignInThrottle).where(SignInThrottle.key_hash == throttle_key(email))
        )
        session.commit()


def test_parallel_attempts_never_pass_the_limit(db_engine: Engine, race_email: str) -> None:
    requests = throttle.MAX_ATTEMPTS * 4
    barrier = threading.Barrier(requests)
    allowed: list[bool] = []
    lock = threading.Lock()
    errors: list[BaseException] = []

    def attempt() -> None:
        try:
            with Session(db_engine) as session:
                barrier.wait(timeout=10)
                result = throttle.begin_attempt(session, race_email)
                session.commit()
            with lock:
                allowed.append(result.allowed)
        except BaseException as exc:  # surfaced below; a thread cannot raise into pytest
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(requests)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(allowed) == requests
    assert allowed.count(True) == throttle.MAX_ATTEMPTS
    with Session(db_engine) as session:
        assert throttle.is_locked(session, race_email)
