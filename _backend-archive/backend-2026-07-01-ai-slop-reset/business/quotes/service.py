from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import Quote
from backend.db.models.enums import QuoteStatus
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class QuoteService:
    """Business logic for customer quotes / estimates."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, Quote, tenant_id)

    async def create_quote(self, data: dict[str, Any]) -> Quote:
        data = dict(data)
        status = data.get("status", QuoteStatus.SENT)
        # A quote that's already "sent" starts the follow-up clock now.
        if status == QuoteStatus.SENT and not data.get("sent_at"):
            data["sent_at"] = datetime.utcnow()
        quote = await self._repo.create(**data)
        logger.info(
            "quote.created", quote_id=str(quote.id), tenant_id=str(self._tenant_id)
        )
        return quote

    async def get_quote(self, quote_id: UUID) -> Quote:
        quote = await self._repo.get_by_id(quote_id)
        if quote is None:
            raise ValueError(f"Quote {quote_id} not found")
        return quote

    async def list_quotes(
        self,
        status: Optional[QuoteStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Quote]:
        stmt = select(Quote).where(Quote.tenant_id == self._tenant_id)
        if status is not None:
            stmt = stmt.where(Quote.status == status)
        stmt = stmt.order_by(Quote.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def set_status(self, quote_id: UUID, status: QuoteStatus) -> Quote:
        quote = await self.get_quote(quote_id)
        quote.status = status
        now = datetime.utcnow()
        if status == QuoteStatus.ACCEPTED:
            quote.accepted_at = now
        elif status == QuoteStatus.DECLINED:
            quote.declined_at = now
        elif status == QuoteStatus.SENT and not quote.sent_at:
            quote.sent_at = now
        await self._session.flush()
        logger.info(
            "quote.status_changed", quote_id=str(quote_id), status=status.value
        )
        return quote
