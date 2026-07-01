from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import NotificationLog
from backend.db.models.enums import NotificationChannel
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, NotificationLog, tenant_id)

    async def send_notification(
        self,
        channel: NotificationChannel,
        recipient: str,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
    ) -> NotificationLog:
        if channel == NotificationChannel.SMS:
            result = await self.send_sms(recipient, content or "")
        elif channel == NotificationChannel.EMAIL:
            result = await self.send_email(recipient, subject or "", content or "")
        elif channel == NotificationChannel.SLACK:
            result = await self.send_slack(recipient, content or "")
        else:
            result = {"status": "pending", "success": True}

        log_entry = await self._repo.create(
            channel=channel,
            recipient=recipient,
            subject=subject,
            content=content,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            status=result.get("status", "pending"),
            error_message=result.get("error"),
            provider_message_id=result.get("provider_message_id"),
            delivered_at=datetime.utcnow() if result.get("success") else None,
        )
        logger.info(
            "notification.sent",
            notification_id=str(log_entry.id),
            channel=channel.value,
            recipient=recipient,
            status=log_entry.status,
        )
        return log_entry

    async def send_sms(self, to: str, message: str) -> dict[str, Any]:
        logger.info("notification.sms.send", to=to, body_preview=message[:60])
        return {
            "success": True,
            "status": "sent",
            "provider_message_id": None,
        }

    async def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        logger.info(
            "notification.email.send",
            to=to,
            subject=subject,
            body_preview=body[:100],
        )
        return {
            "success": True,
            "status": "sent",
            "provider_message_id": None,
        }

    async def send_slack(self, webhook_url: str, message: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    webhook_url,
                    json={"text": message},
                )
            if resp.status_code in (200, 201, 204):
                return {"success": True, "status": "sent"}
            return {
                "success": False,
                "status": "failed",
                "error": f"slack {resp.status_code}: {resp.text[:200]}",
            }
        except Exception as exc:
            logger.error("notification.slack.error", error=str(exc))
            return {"success": False, "status": "failed", "error": str(exc)}

    async def get_notification_logs(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[NotificationLog], int]:
        query = select(NotificationLog).where(
            NotificationLog.tenant_id == self._tenant_id
        )
        count_query = select(func.count()).select_from(NotificationLog).where(
            NotificationLog.tenant_id == self._tenant_id
        )

        if filters:
            if filters.get("channel"):
                query = query.where(NotificationLog.channel == filters["channel"])
                count_query = count_query.where(NotificationLog.channel == filters["channel"])
            if filters.get("status"):
                query = query.where(NotificationLog.status == filters["status"])
                count_query = count_query.where(NotificationLog.status == filters["status"])
            if filters.get("event_type"):
                query = query.where(NotificationLog.event_type == filters["event_type"])
                count_query = count_query.where(NotificationLog.event_type == filters["event_type"])
            if filters.get("date_from"):
                date_from = filters["date_from"]
                if isinstance(date_from, str):
                    date_from = datetime.fromisoformat(date_from)
                query = query.where(NotificationLog.created_at >= date_from)
                count_query = count_query.where(NotificationLog.created_at >= date_from)
            if filters.get("date_to"):
                date_to = filters["date_to"]
                if isinstance(date_to, str):
                    date_to = datetime.fromisoformat(date_to)
                query = query.where(NotificationLog.created_at <= date_to)
                count_query = count_query.where(NotificationLog.created_at <= date_to)

        query = query.order_by(NotificationLog.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        items = result.scalars().all()

        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        return items, total

    async def get_notification_stats(self) -> list[dict[str, Any]]:
        query = select(
            NotificationLog.channel,
            NotificationLog.status,
            func.count().label("count"),
        ).where(
            NotificationLog.tenant_id == self._tenant_id
        ).group_by(
            NotificationLog.channel,
            NotificationLog.status,
        )
        result = await self._session.execute(query)
        rows = result.all()

        stats: dict[str, dict[str, int]] = {}
        for row in rows:
            channel = row.channel.value if hasattr(row.channel, "value") else str(row.channel)
            if channel not in stats:
                stats[channel] = {}
            stats[channel][row.status] = row.count

        return [{"channel": ch, **counts} for ch, counts in stats.items()]
