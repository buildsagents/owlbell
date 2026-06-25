from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import CallerProfile
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit() or c == "+")


def _hash_phone(phone: str) -> str:
    return hashlib.sha256(_normalize_phone(phone).encode()).hexdigest()


class CRMService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, CallerProfile, tenant_id)

    async def get_or_create_profile(self, phone_number: str) -> CallerProfile:
        phone_hash = _hash_phone(phone_number)
        query = select(CallerProfile).where(
            CallerProfile.tenant_id == self._tenant_id,
            CallerProfile.phone_hash == phone_hash,
        )
        result = await self._session.execute(query)
        profile = result.scalar_one_or_none()

        if profile is None:
            profile = await self._repo.create(
                phone_number=phone_number,
                phone_hash=phone_hash,
            )
            logger.info(
                "crm.profile_created",
                profile_id=str(profile.id),
                phone_hash=phone_hash,
                tenant_id=str(self._tenant_id),
            )

        return profile

    async def update_profile(self, profile_id: UUID, data: dict[str, Any]) -> CallerProfile:
        profile = await self._repo.get_by_id(profile_id)
        if profile is None:
            raise ValueError(f"CallerProfile {profile_id} not found")

        if "tags" in data:
            profile.tags_json = data.pop("tags")
        if "notes" in data:
            existing = profile.notes or ""
            profile.notes = data.pop("notes")

        for key, value in data.items():
            setattr(profile, key, value)

        await self._session.flush()
        logger.info(
            "crm.profile_updated",
            profile_id=str(profile_id),
            tenant_id=str(self._tenant_id),
        )
        return profile

    async def search_profiles(self, query: str) -> Sequence[CallerProfile]:
        pattern = f"%{query}%"
        stmt = select(CallerProfile).where(
            CallerProfile.tenant_id == self._tenant_id,
            or_(
                CallerProfile.phone_number.ilike(pattern),
                CallerProfile.name.ilike(pattern),
                CallerProfile.email.ilike(pattern),
            ),
        ).order_by(CallerProfile.last_call_at.desc().nullslast())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_recent_callers(self, limit: int = 20) -> Sequence[CallerProfile]:
        stmt = select(CallerProfile).where(
            CallerProfile.tenant_id == self._tenant_id,
            CallerProfile.last_call_at.isnot(None),
        ).order_by(
            CallerProfile.last_call_at.desc()
        ).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add_note(self, profile_id: UUID, note: str) -> CallerProfile:
        profile = await self._repo.get_by_id(profile_id)
        if profile is None:
            raise ValueError(f"CallerProfile {profile_id} not found")

        timestamp = datetime.utcnow().isoformat()
        new_entry = f"[{timestamp}] {note}"
        if profile.notes:
            profile.notes += f"\n{new_entry}"
        else:
            profile.notes = new_entry

        await self._session.flush()
        logger.info(
            "crm.note_added",
            profile_id=str(profile_id),
            tenant_id=str(self._tenant_id),
        )
        return profile
