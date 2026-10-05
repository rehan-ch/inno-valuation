"""factory-boy factories. One factory per model, all subclassing ``BaseFactory``.

No models yet (Phase 0). The ``db`` fixture binds the per-test session with
``bind_session``, so factories write inside the test transaction.
"""

from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.orm import Session

_session: Session | None = None


def bind_session(session: Session | None) -> None:
    global _session
    _session = session


def _get_session() -> Session:
    if _session is None:
        raise RuntimeError("Factories need the `db` fixture (no session bound).")
    return _session


class BaseFactory(SQLAlchemyModelFactory):  # type: ignore[misc]
    class Meta:
        abstract = True
        sqlalchemy_session_factory = _get_session
        sqlalchemy_session_persistence = "flush"
