"""Shared fixtures.

ENVIRONMENT is forced to "test" before any app module is imported, so Celery runs eagerly.
Database fixtures are lazy and opt-in: tests that do not request ``db`` or ``client``
(for example tests/scoring) never touch Postgres.
"""

import os

os.environ["ENVIRONMENT"] = "test"

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.emails.backends import MemoryEmailBackend, override_email_backend
from app.jobs.db import override_task_session
from tests import factories
from tests.database import alembic_config, throwaway_database


@pytest.fixture(autouse=True)
def _never_open_a_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """The development email backend opens emails in a browser tab; a test never may."""

    def refuse(*args: object, **kwargs: object) -> bool:
        raise AssertionError("A test tried to open a browser tab.")

    monkeypatch.setattr("webbrowser.open", refuse)
    monkeypatch.setattr("webbrowser.open_new_tab", refuse)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Create a throwaway database on TEST_DATABASE_URL's server, migrate it, drop it after."""
    with throwaway_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture(scope="session")
def db_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """A session inside an outer transaction that is rolled back after the test.

    Service code may call ``commit()``; it only releases a savepoint. Celery tasks (eager in
    tests) use this same session, so they see the rows the request just wrote.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    factories.bind_session(session)

    @contextmanager
    def _task_session() -> Iterator[Session]:
        yield session  # not closed here: the test owns it

    override_task_session(_task_session)
    try:
        yield session
    finally:
        override_task_session(None)
        factories.bind_session(None)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def outbox() -> Iterator[MemoryEmailBackend]:
    """Emails sent during the test (Celery runs eagerly, so they arrive at once)."""
    backend = MemoryEmailBackend()
    override_email_backend(backend)
    try:
        yield backend
    finally:
        override_email_backend(None)


@pytest.fixture
def client(db: Session, outbox: MemoryEmailBackend) -> Iterator[TestClient]:
    # Imported late on purpose: ENVIRONMENT=test must be set before the app loads.
    from app.main import app  # noqa: PLC0415

    def _override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
