from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import CallerProfile
from backend.db.models.call import Call
from backend.db.models.enums import CallStatus, NotificationChannel
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class MessageService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, Call, tenant_id)

    async def create_message(self, data: dict[str, Any]) -> Call:
        data.setdefault("voicemail_left", True)
        data.setdefault("status", CallStatus.VOICEMAIL)
        message = await self._repo.create(**data)
        logger.info(
            "message.created",
            message_id=str(message.id),
            tenant_id=str(self._tenant_id),
        )
        return message

    async def get_message(self, message_id: UUID) -> Call:
        message = await self._repo.get_by_id(message_id)
        if message is None:
            raise ValueError(f"Message (call) {message_id} not found")
        return message

    async def list_messages(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Call], int]:
        query = select(Call).where(
            Call.tenant_id == self._tenant_id,
            Call.voicemail_left == True,
        )
        count_query = select(func.count()).select_from(Call).where(
            Call.tenant_id == self._tenant_id,
            Call.voicemail_left == True,
        )

        if filters:
            if filters.get("caller_number"):
                query = query.where(Call.caller_number == filters["caller_number"])
                count_query = count_query.where(Call.caller_number == filters["caller_number"])
            if filters.get("status"):
                query = query.where(Call.status == filters["status"])
                count_query = count_query.where(Call.status == filters["status"])
            if filters.get("date_from"):
                date_from = filters["date_from"]
                if isinstance(date_from, str):
                    date_from = datetime.fromisoformat(date_from)
                query = query.where(Call.started_at >= date_from)
                count_query = count_query.where(Call.started_at >= date_from)
            if filters.get("date_to"):
                date_to = filters["date_to"]
                if isinstance(date_to, str):
                    date_to = datetime.fromisoformat(date_to)
                query = query.where(Call.started_at <= date_to)
                count_query = count_query.where(Call.started_at <= date_to)
            if filters.get("search"):
                pattern = f"%{filters['search']}%"
                query = query.where(
                    or_(
                        Call.caller_name.ilike(pattern),
                        Call.caller_number.ilike(pattern),
                    )
                )
                count_query = count_query.where(
                    or_(
                        Call.caller_name.ilike(pattern),
                        Call.caller_number.ilike(pattern),
                    )
                )

        query = query.order_by(Call.started_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        items = result.scalars().all()

        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        return items, total

    async def update_message(self, message_id: UUID, data: dict[str, Any]) -> Call:
        message = await self._repo.update(message_id, **data)
        if message is None:
            raise ValueError(f"Message (call) {message_id} not found")
        logger.info(
            "message.updated",
            message_id=str(message_id),
            tenant_id=str(self._tenant_id),
        )
        return message

    async def mark_read(self, message_id: UUID, user_id: UUID) -> Call:
        message = await self.get_message(message_id)
        metadata = dict(message.metadata_json or {})
        read_by = metadata.get("read_by", [])
        read_by.append({
            "user_id": str(user_id),
            "read_at": datetime.utcnow().isoformat(),
        })
        metadata["read_by"] = read_by
        message.metadata_json = metadata
        message.metadata_json["read_count"] = len(read_by)
        await self._session.flush()
        logger.info(
            "message.marked_read",
            message_id=str(message_id),
            user_id=str(user_id),
        )
        return message

    async def forward_message(self, message_id: UUID, destinations: list[str]) -> Call:
        message = await self.get_message(message_id)
        metadata = dict(message.metadata_json or {})
        forwards = metadata.get("forwards", [])
        for dest in destinations:
            forwards.append({
                "destination": dest,
                "forwarded_at": datetime.utcnow().isoformat(),
            })
        metadata["forwards"] = forwards
        message.metadata_json = metadata
        await self._session.flush()
        logger.info(
            "message.forwarded",
            message_id=str(message_id),
            destinations=destinations,
        )
        return message

    async def resolve_message(self, message_id: UUID, note: str) -> Call:
        message = await self.get_message(message_id)
        metadata = dict(message.metadata_json or {})
        metadata["resolved_at"] = datetime.utcnow().isoformat()
        metadata["resolution_note"] = note
        message.metadata_json = metadata
        message.metadata_json["resolved"] = True
        await self._session.flush()
        logger.info(
            "message.resolved",
            message_id=str(message_id),
        )
        return message

    async def get_message_stats(self) -> list[dict[str, Any]]:
        query = select(
            Call.status,
            func.count().label("count"),
        ).where(
            Call.tenant_id == self._tenant_id,
            Call.voicemail_left == True,
        ).group_by(Call.status)
        result = await self._session.execute(query)
        rows = result.all()

        channel_query = select(
            Call.status,
            func.count().label("count"),
        ).where(
            Call.tenant_id == self._tenant_id,
            Call.voicemail_left == True,
        ).group_by(Call.status)
        channel_result = await self._session.execute(channel_query)
        channel_rows = channel_result.all()

        total_query = select(func.count()).select_from(Call).where(
            Call.tenant_id == self._tenant_id,
            Call.voicemail_left == True,
        )
        total_result = await self._session.execute(total_query)
        total = total_result.scalar_one()

        return [
            {"status": row.status, "count": row.count}
            for row in rows
        ] + [{"total": total}]

    async def delete_message(self, message_id: UUID) -> None:
        message = await self._repo.get_by_id(message_id)
        if message is None:
            raise ValueError(f"Message (call) {message_id} not found")
        message.voicemail_left = False
        await self._session.flush()
        logger.info(
            "message.deleted",
            message_id=str(message_id),
            tenant_id=str(self._tenant_id),
        )
