"""
Owlbell — Database CRUD Helpers.

Reusable async CRUD operations for all SQLAlchemy models.
All functions take an AsyncSession and return real DB data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


# ---------------------------------------------------------------------------
# Generic CRUD
# ---------------------------------------------------------------------------


async def create(db: AsyncSession, model: Type[ModelType], **kwargs) -> ModelType:
    """Create a new record and return it."""
    instance = model(**kwargs)
    db.add(instance)
    await db.flush()
    await db.refresh(instance)
    return instance


async def get_by_id(
    db: AsyncSession, model: Type[ModelType], record_id: uuid.UUID
) -> Optional[ModelType]:
    """Get a single record by primary key."""
    result = await db.execute(select(model).where(model.id == record_id))
    return result.scalar_one_or_none()


async def get_by_field(
    db: AsyncSession, model: Type[ModelType], field: str, value: Any
) -> Optional[ModelType]:
    """Get a single record by an arbitrary field."""
    column = getattr(model, field)
    result = await db.execute(select(model).where(column == value))
    return return_first(result)


async def list_all(
    db: AsyncSession,
    model: Type[ModelType],
    *,
    tenant_id: Optional[uuid.UUID] = None,
    filters: Optional[List] = None,
    order_by: Optional[Any] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[ModelType]:
    """List records with optional tenant filtering, filters, and pagination."""
    query = select(model)
    if tenant_id is not None and hasattr(model, "tenant_id"):
        query = query.where(model.tenant_id == tenant_id)
    if filters:
        query = query.where(and_(*filters))
    if order_by is not None:
        query = query.order_by(order_by)
    else:
        # Default to created_at desc if the model has it
        if hasattr(model, "created_at"):
            query = query.order_by(model.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def update_record(
    db: AsyncSession, model: Type[ModelType], record_id: uuid.UUID, **kwargs
) -> Optional[ModelType]:
    """Update a record by ID and return it."""
    kwargs["updated_at"] = datetime.now(timezone.utc)
    await db.execute(update(model).where(model.id == record_id).values(**kwargs))
    await db.flush()
    return await get_by_id(db, model, record_id)


async def delete_record(
    db: AsyncSession, model: Type[ModelType], record_id: uuid.UUID
) -> bool:
    """Delete a record by ID. Returns True if deleted."""
    result = await db.execute(delete(model).where(model.id == record_id))
    return result.rowcount > 0


async def count(
    db: AsyncSession,
    model: Type[ModelType],
    *,
    tenant_id: Optional[uuid.UUID] = None,
    filters: Optional[List] = None,
) -> int:
    """Count records with optional filters."""
    query = select(func.count()).select_from(model)
    if tenant_id is not None and hasattr(model, "tenant_id"):
        query = query.where(model.tenant_id == tenant_id)
    if filters:
        query = query.where(and_(*filters))
    result = await db.execute(query)
    return result.scalar()


async def exists(
    db: AsyncSession, model: Type[ModelType], **kwargs
) -> bool:
    """Check if a record exists matching the given field values."""
    query = select(func.count()).select_from(model)
    for field, value in kwargs.items():
        column = getattr(model, field)
        query = query.where(column == value)
    result = await db.execute(query)
    return result.scalar() > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def return_first(result) -> Optional[Any]:
    """Extract first scalar from a SQLAlchemy result."""
    try:
        return result.scalar_one()
    except Exception:
        return None


def to_dict(instance) -> Dict[str, Any]:
    """Convert a SQLAlchemy model instance to a dict (JSON-serializable)."""
    if instance is None:
        return {}
    d = {}
    for column in instance.__table__.columns:
        val = getattr(instance, column.name)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        d[column.name] = val
    return d


def to_dict_list(instances) -> List[Dict[str, Any]]:
    """Convert a list of model instances to a list of dicts."""
    return [to_dict(i) for i in instances]
