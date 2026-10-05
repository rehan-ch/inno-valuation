"""FastAPI dependencies shared by every router.

Phase 0 exposes only ``get_db``. ``current_user``, ``current_org`` and
``require_role(...)`` arrive in Phase 2. The organisation must always come from
``current_org``, never from a path or query parameter.
"""

from app.db.session import get_db

__all__ = ["get_db"]
