from __future__ import annotations

from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import CallSummary
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class SummarizerService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, CallSummary, tenant_id)

    async def create_summary(self, call_id: UUID, data: dict[str, Any]) -> CallSummary:
        data["call_id"] = call_id
        summary = await self._repo.create(**data)
        logger.info(
            "summary.created",
            summary_id=str(summary.id),
            call_id=str(call_id),
            tenant_id=str(self._tenant_id),
        )
        return summary

    async def get_summary(self, call_id: UUID) -> CallSummary:
        stmt = select(CallSummary).where(
            CallSummary.tenant_id == self._tenant_id,
            CallSummary.call_id == call_id,
        )
        result = await self._session.execute(stmt)
        summary = result.scalar_one_or_none()
        if summary is None:
            raise ValueError(f"CallSummary for call {call_id} not found")
        return summary

    async def update_summary(self, call_id: UUID, data: dict[str, Any]) -> CallSummary:
        stmt = select(CallSummary).where(
            CallSummary.tenant_id == self._tenant_id,
            CallSummary.call_id == call_id,
        )
        result = await self._session.execute(stmt)
        summary = result.scalar_one_or_none()
        if summary is None:
            raise ValueError(f"CallSummary for call {call_id} not found")

        for key, value in data.items():
            setattr(summary, key, value)

        await self._session.flush()
        logger.info(
            "summary.updated",
            call_id=str(call_id),
            tenant_id=str(self._tenant_id),
        )
        return summary

    async def list_summaries(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[CallSummary], int]:
        query = select(CallSummary).where(
            CallSummary.tenant_id == self._tenant_id
        )
        count_query = select(func.count()).select_from(CallSummary).where(
            CallSummary.tenant_id == self._tenant_id
        )

        if filters:
            if filters.get("sentiment"):
                query = query.where(CallSummary.sentiment == filters["sentiment"])
                count_query = count_query.where(CallSummary.sentiment == filters["sentiment"])
            if filters.get("primary_intent"):
                query = query.where(CallSummary.primary_intent == filters["primary_intent"])
                count_query = count_query.where(CallSummary.primary_intent == filters["primary_intent"])

        query = query.order_by(CallSummary.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        items = result.scalars().all()

        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        return items, total
