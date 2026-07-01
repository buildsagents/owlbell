"""
Owlbell — Database Layer

Complete database layer including:
- SQLAlchemy 2.0 models with multi-tenant isolation
- Session factory (``backend.db.session`` — single source of truth)
- Repository pattern with tenant scoping
- Redis cache client with decorators
- Alembic async migration configuration
"""

from backend.db.session import (
    dispose_engine,
    get_db_session,
    get_engine,
    get_session_maker,
    init_engine,
    open_db_session,
    require_session_maker,
)

__all__ = [
    "dispose_engine",
    "get_db_session",
    "get_engine",
    "get_session_maker",
    "init_engine",
    "open_db_session",
    "require_session_maker",
]
