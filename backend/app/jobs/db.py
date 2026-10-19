"""Database sessions for Celery tasks. A task opens its own session; it never shares the
request's session.

Tests run tasks eagerly inside the request, against a throwaway database inside one rolled
back transaction, so they point ``task_session`` at the test session with
``override_task_session``.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy.orm import Session

from app.db.session import SessionLocal

SessionFactory = Callable[[], AbstractContextManager[Session]]


@contextmanager
def _new_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


_factory: SessionFactory = _new_session


def task_session() -> AbstractContextManager[Session]:
    return _factory()


def override_task_session(factory: SessionFactory | None) -> None:
    global _factory  # noqa: PLW0603
    _factory = factory or _new_session
