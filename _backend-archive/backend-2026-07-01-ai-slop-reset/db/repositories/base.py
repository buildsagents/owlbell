"""
Generic repository base with CRUD operations.

Location: backend/db/repositories/base.py

Provides:
- ``BaseRepository``: Generic async CRUD for any SQLAlchemy model
- ``TenantScopedRepository``: Automatic tenant_id filtering on all queries

Usage in FastAPI endpoints:
    async def get_calls(
        session: AsyncSession = Depends(get_db_session),
    ):
        repo = TenantScopedRepository(session, Call, tenant_id)
        return await repo.get_all(limit=50)
"""

from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async CRUD repository.

    Provides standard create, read, update, and delete operations
    for any SQLAlchemy model. Does **not** enforce tenant isolation —
    use ``TenantScopedRepository`` for multi-tenant queries.
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        """Initialize the repository.

        Args:
            session: The async SQLAlchemy session.
            model: The SQLAlchemy model class this repository manages.
        """
        self._session = session
        self._model = model

    # ── Create ────────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record.

        Flushes the session to populate auto-generated fields
        (e.g., ``id``) without committing the transaction.

        Args:
            **kwargs: Column values for the new record.

        Returns:
            The newly created model instance.
        """
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def create_many(
        self, items: list[dict[str, Any]]
    ) -> list[ModelType]:
        """Bulk insert multiple records.

        Args:
            items: List of dicts, each containing column values.

        Returns:
            The list of created model instances.
        """
        instances = [self._model(**item) for item in items]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    # ── Read ──────────────────────────────────────────────────────

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """Get a record by primary key.

        Args:
            id: The UUID primary key.

        Returns:
            The model instance or ``None`` if not found.
        """
        result = await self._session.execute(
            select(self._model).where(self._model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[UUID]) -> Sequence[ModelType]:
        """Get multiple records by primary keys.

        Args:
            ids: List of UUID primary keys.

        Returns:
            Sequence of matching model instances (may be empty).
        """
        result = await self._session.execute(
            select(self._model).where(self._model.id.in_(ids))
        )
        return result.scalars().all()

    async def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[Any] = None,
    ) -> Sequence[ModelType]:
        """Get all records with pagination.

        Args:
            limit: Maximum rows to return.
            offset: Rows to skip.
            order_by: Optional ORDER BY clause.

        Returns:
            Sequence of model instances.
        """
        query = select(self._model)
        if order_by is not None:
            query = query.order_by(order_by)
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        """Count all records.

        Returns:
            Total number of rows in the table.
        """
        result = await self._session.execute(
            select(func.count()).select_from(self._model)
        )
        return result.scalar_one()

    # ── Update ────────────────────────────────────────────────────

    async def update(
        self, id: UUID, **kwargs: Any
    ) -> Optional[ModelType]:
        """Update a record by ID.

        Args:
            id: The UUID primary key.
            **kwargs: Column values to update.

        Returns:
            The updated model instance, or ``None`` if not found.
        """
        await self._session.execute(
            update(self._model)
            .where(self._model.id == id)
            .values(**kwargs)
        )
        return await self.get_by_id(id)

    async def update_many(
        self, ids: list[UUID], **kwargs: Any
    ) -> int:
        """Update multiple records.

        Args:
            ids: List of UUID primary keys to update.
            **kwargs: Column values to update.

        Returns:
            Number of rows updated.
        """
        result = await self._session.execute(
            update(self._model)
            .where(self._model.id.in_(ids))
            .values(**kwargs)
        )
        return result.rowcount  # type: ignore[return-value]

    # ── Delete ────────────────────────────────────────────────────

    async def delete(self, id: UUID) -> bool:
        """Hard delete a record.

        Args:
            id: The UUID primary key.

        Returns:
            ``True`` if a row was deleted.
        """
        result = await self._session.execute(
            delete(self._model).where(self._model.id == id)
        )
        return result.rowcount > 0  # type: ignore[return-value]

    async def delete_many(self, ids: list[UUID]) -> int:
        """Hard delete multiple records.

        Args:
            ids: List of UUID primary keys.

        Returns:
            Number of rows deleted.
        """
        result = await self._session.execute(
            delete(self._model).where(self._model.id.in_(ids))
        )
        return result.rowcount  # type: ignore[return-value]

    # ── Existence ─────────────────────────────────────────────────

    async def exists(self, id: UUID) -> bool:
        """Check if a record exists.

        Args:
            id: The UUID primary key.

        Returns:
            ``True`` if the record exists.
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(self._model)
            .where(self._model.id == id)
        )
        return result.scalar_one() > 0


class TenantScopedRepository(BaseRepository[ModelType]):
    """Repository base that enforces ``tenant_id`` filtering on all queries.

    All read and write operations automatically include a filter for
    the tenant ID, ensuring row-level data isolation in the multi-tenant
    schema. The ``create`` and ``create_many`` methods automatically
    inject the tenant ID into new records.

    Args:
        session: The async SQLAlchemy session.
        model: The SQLAlchemy model class.
        tenant_id: The UUID of the tenant to scope all queries to.
    """

    def __init__(
        self,
        session: AsyncSession,
        model: Type[ModelType],
        tenant_id: UUID,
    ):
        super().__init__(session, model)
        self._tenant_id = tenant_id
        self._tenant_filter = model.tenant_id == tenant_id

    # ── Create (with tenant injection) ────────────────────────────

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record with automatic tenant_id injection."""
        kwargs.setdefault("tenant_id", self._tenant_id)
        return await super().create(**kwargs)

    async def create_many(
        self, items: list[dict[str, Any]]
    ) -> list[ModelType]:
        """Bulk insert with automatic tenant_id injection."""
        for item in items:
            item.setdefault("tenant_id", self._tenant_id)
        return await super().create_many(items)

    # ── Read (with tenant filter) ─────────────────────────────────

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """Get a record by primary key within the tenant scope."""
        result = await self._session.execute(
            select(self._model)
            .where(self._model.id == id)
            .where(self._tenant_filter)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[UUID]) -> Sequence[ModelType]:
        """Get multiple records by primary key within the tenant scope."""
        result = await self._session.execute(
            select(self._model)
            .where(self._model.id.in_(ids))
            .where(self._tenant_filter)
        )
        return result.scalars().all()

    async def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[Any] = None,
    ) -> Sequence[ModelType]:
        """Get all records for the tenant with pagination."""
        query = select(self._model).where(self._tenant_filter)
        if order_by is not None:
            query = query.order_by(order_by)
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        """Count all records for the tenant."""
        result = await self._session.execute(
            select(func.count())
            .select_from(self._model)
            .where(self._tenant_filter)
        )
        return result.scalar_one()

    # ── Update (with tenant filter) ───────────────────────────────

    async def update(
        self, id: UUID, **kwargs: Any
    ) -> Optional[ModelType]:
        """Update a record within the tenant scope."""
        await self._session.execute(
            update(self._model)
            .where(self._model.id == id)
            .where(self._tenant_filter)
            .values(**kwargs)
        )
        return await self.get_by_id(id)

    # ── Delete (with tenant filter) ───────────────────────────────

    async def delete(self, id: UUID) -> bool:
        """Delete a record within the tenant scope."""
        result = await self._session.execute(
            delete(self._model)
            .where(self._model.id == id)
            .where(self._tenant_filter)
        )
        return result.rowcount > 0  # type: ignore[return-value]
