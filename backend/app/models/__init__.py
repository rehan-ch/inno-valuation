"""SQLAlchemy models, one module per table group.

Import every model module here so ``Base.metadata`` is complete for Alembic.
No models yet (Phase 0).
"""

from app.db.base import Base

__all__ = ["Base"]
