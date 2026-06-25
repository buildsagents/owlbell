from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import FAQEntry
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, FAQEntry, tenant_id)

    async def create_faq(self, data: dict[str, Any]) -> FAQEntry:
        entry = await self._repo.create(**data)
        logger.info(
            "knowledge.faq_created",
            faq_id=str(entry.id),
            tenant_id=str(self._tenant_id),
        )
        return entry

    async def update_faq(self, faq_id: UUID, data: dict[str, Any]) -> FAQEntry:
        entry = await self._repo.get_by_id(faq_id)
        if entry is None:
            raise ValueError(f"FAQEntry {faq_id} not found")

        for key, value in data.items():
            setattr(entry, key, value)

        await self._session.flush()
        logger.info(
            "knowledge.faq_updated",
            faq_id=str(faq_id),
            tenant_id=str(self._tenant_id),
        )
        return entry

    async def delete_faq(self, faq_id: UUID) -> None:
        entry = await self._repo.get_by_id(faq_id)
        if entry is None:
            raise ValueError(f"FAQEntry {faq_id} not found")
        entry.deleted_at = datetime.utcnow()
        await self._session.flush()
        logger.info(
            "knowledge.faq_deleted",
            faq_id=str(faq_id),
            tenant_id=str(self._tenant_id),
        )

    async def get_faq(self, faq_id: UUID) -> FAQEntry:
        entry = await self._repo.get_by_id(faq_id)
        if entry is None or entry.deleted_at is not None:
            raise ValueError(f"FAQEntry {faq_id} not found")
        return entry

    async def list_faqs(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[FAQEntry], int]:
        query = select(FAQEntry).where(
            FAQEntry.tenant_id == self._tenant_id,
            FAQEntry.deleted_at.is_(None),
        )
        count_query = select(func.count()).select_from(FAQEntry).where(
            FAQEntry.tenant_id == self._tenant_id,
            FAQEntry.deleted_at.is_(None),
        )

        if category:
            query = query.where(FAQEntry.category == category)
            count_query = count_query.where(FAQEntry.category == category)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    FAQEntry.question.ilike(pattern),
                    FAQEntry.answer.ilike(pattern),
                )
            )
            count_query = count_query.where(
                or_(
                    FAQEntry.question.ilike(pattern),
                    FAQEntry.answer.ilike(pattern),
                )
            )

        query = query.order_by(FAQEntry.use_count.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        items = result.scalars().all()

        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        return items, total

    async def search_faqs(self, query: str) -> Sequence[FAQEntry]:
        pattern = f"%{query}%"
        stmt = select(FAQEntry).where(
            FAQEntry.tenant_id == self._tenant_id,
            FAQEntry.deleted_at.is_(None),
            FAQEntry.is_active == True,
            or_(
                FAQEntry.question.ilike(pattern),
                FAQEntry.answer.ilike(pattern),
            ),
        ).order_by(FAQEntry.use_count.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def increment_usage(self, faq_id: UUID) -> FAQEntry:
        entry = await self._repo.get_by_id(faq_id)
        if entry is None or entry.deleted_at is not None:
            raise ValueError(f"FAQEntry {faq_id} not found")
        entry.use_count = (entry.use_count or 0) + 1
        entry.last_used_at = datetime.utcnow()
        await self._session.flush()
        return entry
