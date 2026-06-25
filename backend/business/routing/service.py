from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import RoutingRule
from backend.db.models.enums import RoutingType
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class RoutingService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, RoutingRule, tenant_id)

    async def create_rule(self, data: dict[str, Any]) -> RoutingRule:
        rule = await self._repo.create(**data)
        logger.info(
            "routing.rule_created",
            rule_id=str(rule.id),
            name=rule.name,
            priority=rule.priority,
        )
        return rule

    async def list_rules(self) -> Sequence[RoutingRule]:
        return await self._repo.get_all(
            order_by=RoutingRule.priority,
        )

    async def update_rule(self, rule_id: UUID, data: dict[str, Any]) -> RoutingRule:
        rule = await self._repo.update(rule_id, **data)
        if rule is None:
            raise ValueError(f"RoutingRule {rule_id} not found")
        logger.info(
            "routing.rule_updated",
            rule_id=str(rule_id),
            tenant_id=str(self._tenant_id),
        )
        return rule

    async def delete_rule(self, rule_id: UUID) -> None:
        deleted = await self._repo.delete(rule_id)
        if not deleted:
            raise ValueError(f"RoutingRule {rule_id} not found")
        logger.info(
            "routing.rule_deleted",
            rule_id=str(rule_id),
            tenant_id=str(self._tenant_id),
        )

    async def reorder_rules(self, rule_ids: list[UUID]) -> list[RoutingRule]:
        rules = await self._repo.get_by_ids(rule_ids)
        found = {r.id: r for r in rules}

        for i, rid in enumerate(rule_ids):
            rule = found.get(rid)
            if rule is not None:
                rule.priority = (i + 1) * 10

        await self._session.flush()
        logger.info(
            "routing.rules_reordered",
            rule_ids=[str(r) for r in rule_ids],
        )
        return sorted(rules, key=lambda r: r.priority)

    async def evaluate_routing(
        self,
        caller_number: str,
        time: Optional[datetime] = None,
        intent: Optional[str] = None,
    ) -> Optional[RoutingRule]:
        now = time or datetime.utcnow()

        stmt = select(RoutingRule).where(
            RoutingRule.tenant_id == self._tenant_id,
            RoutingRule.is_active == True,
            RoutingRule.effective_from <= now,
            or_(
                RoutingRule.effective_to.is_(None),
                RoutingRule.effective_to >= now,
            ),
        ).order_by(RoutingRule.priority)

        result = await self._session.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            conditions = rule.conditions_json or {}

            if rule.rule_type == RoutingType.CALLER_ID:
                numbers = conditions.get("numbers", [])
                if caller_number in numbers:
                    return rule

            if rule.rule_type == RoutingType.INTENT_BASED:
                if intent and conditions.get("intents"):
                    if intent in conditions["intents"]:
                        return rule

            if rule.rule_type == RoutingType.DEFAULT:
                return rule

        return None

    async def record_match(self, rule_id: UUID) -> RoutingRule:
        rule = await self._repo.get_by_id(rule_id)
        if rule is None:
            raise ValueError(f"RoutingRule {rule_id} not found")
        rule.match_count = (rule.match_count or 0) + 1
        await self._session.flush()
        return rule
