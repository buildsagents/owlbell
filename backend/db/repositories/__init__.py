"""
Repository layer for data access.

Location: backend/db/repositories/__init__.py

Usage in FastAPI endpoints:
    async def get_calls(
        session: AsyncSession = Depends(get_db_session),
    ):
        repo = TenantScopedRepository(session, Call, tenant_id)
        return await repo.get_all(limit=50)
"""

from backend.db.repositories.base import BaseRepository, TenantScopedRepository

__all__ = [
    "BaseRepository",
    "TenantScopedRepository",
]
