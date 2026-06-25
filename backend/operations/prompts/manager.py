"""operations/prompts/manager.py - Prompt versioning and A/B testing.

Manages versioned system prompts per tenant. Supports A/B testing,
rollback, and performance tracking. Each version is immutable -
edits create a new version.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class PromptType(str, Enum):
    """Types of prompts."""
    SYSTEM = "system"
    GREETING = "greeting"
    HOLD = "hold"
    VOICEMAIL = "voicemail"
    TRANSFER = "transfer"
    GOODBYE = "goodbye"
    FALLBACK = "fallback"
    CUSTOM_1 = "custom_1"
    CUSTOM_2 = "custom_2"
    CUSTOM_3 = "custom_3"


class PromptStatus(str, Enum):
    """Status of a prompt version."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    AB_TEST = "ab_test"


class PromptVersion:
    """A versioned prompt.

    Each version is immutable. Edits create a new version.
    Only one version per tenant+type can be active at a time.
    """

    def __init__(
        self,
        tenant_id: uuid.UUID,
        prompt_type: PromptType,
        version_number: int,
        name: str,
        content: str,
        variables: Optional[Dict[str, Any]] = None,
        status: PromptStatus = PromptStatus.DRAFT,
        is_active: bool = False,
        ab_test_group: Optional[str] = None,
        ab_test_id: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
    ):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.prompt_type = prompt_type
        self.version_number = version_number
        self.name = name
        self.content = content
        self.variables = variables or {}
        self.status = status
        self.is_active = is_active
        self.ab_test_group = ab_test_group
        self.ab_test_id = ab_test_id
        self.times_used = 0
        self.avg_call_rating: Optional[float] = None
        self.created_by = created_by
        self.notes = notes
        self.created_at = datetime.utcnow()
        self.activated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "prompt_type": self.prompt_type.value,
            "version_number": self.version_number,
            "name": self.name,
            "content": self.content,
            "variables": self.variables,
            "status": self.status.value,
            "is_active": self.is_active,
            "ab_test_group": self.ab_test_group,
            "ab_test_id": str(self.ab_test_id) if self.ab_test_id else None,
            "times_used": self.times_used,
            "avg_call_rating": self.avg_call_rating,
            "created_by": str(self.created_by) if self.created_by else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
        }


class ABTest:
    """A/B test configuration for prompts."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        name: str,
        prompt_type: PromptType,
        variant_a_id: uuid.UUID,
        variant_b_id: uuid.UUID,
        split_percentage: int = 50,
        description: Optional[str] = None,
    ):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.name = name
        self.description = description
        self.prompt_type = prompt_type
        self.variant_a_id = variant_a_id
        self.variant_b_id = variant_b_id
        self.split_percentage = split_percentage
        self.is_active = True
        self.started_at = datetime.utcnow()
        self.ended_at: Optional[datetime] = None
        self.winning_variant: Optional[str] = None
        self.total_participants = 0
        self.variant_a_calls = 0
        self.variant_b_calls = 0
        self.variant_a_avg_rating: Optional[float] = None
        self.variant_b_avg_rating: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "description": self.description,
            "prompt_type": self.prompt_type.value,
            "variant_a_id": str(self.variant_a_id),
            "variant_b_id": str(self.variant_b_id),
            "split_percentage": self.split_percentage,
            "is_active": self.is_active,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "winning_variant": self.winning_variant,
            "total_participants": self.total_participants,
            "variant_a_calls": self.variant_a_calls,
            "variant_b_calls": self.variant_b_calls,
            "variant_a_avg_rating": self.variant_a_avg_rating,
            "variant_b_avg_rating": self.variant_b_avg_rating,
        }


class PromptManager:
    """Manages prompt versioning and A/B testing.

    Usage:
        manager = PromptManager(session_maker=get_session_maker())
        version = await manager.create_version(tenant_id, PromptType.SYSTEM, "v1", "Hello...")
        await manager.activate_version(version.id)
        ab_test = await manager.create_ab_test(tenant_id, "Test A", PromptType.SYSTEM, v1_id, v2_id)

    When ``session_maker`` is provided, versions and A/B tests are persisted to
    the ``prompt_versions`` / ``prompt_ab_tests`` tables. Without it, state is
    kept in process memory (used by unit tests).

    All public methods return the lightweight ``PromptVersion`` / ``ABTest``
    DTOs regardless of mode, so callers see a stable shape (``.to_dict()``).
    """

    def __init__(self, session_maker: Optional[Callable[[], Any]] = None) -> None:
        self.session_maker = session_maker
        self._versions: Dict[str, PromptVersion] = {}
        self._ab_tests: Dict[str, ABTest] = {}
        self._tenant_counters: Dict[str, Dict[str, int]] = {}

    @property
    def persistent(self) -> bool:
        """True when versions/tests are written through to Postgres."""
        return self.session_maker is not None

    # -- Row <-> DTO mapping ----------------------------------------------

    @staticmethod
    def _version_from_row(row: Any) -> "PromptVersion":
        """Build a PromptVersion DTO from a PromptVersionRecord ORM row."""
        dto = PromptVersion.__new__(PromptVersion)
        dto.id = row.id
        dto.tenant_id = row.tenant_id
        dto.prompt_type = PromptType(row.prompt_type)
        dto.version_number = row.version_number
        dto.name = row.name
        dto.content = row.content
        dto.variables = row.variables_json or {}
        dto.status = PromptStatus(row.status)
        dto.is_active = row.is_active
        dto.ab_test_group = row.ab_test_group
        dto.ab_test_id = row.ab_test_id
        dto.times_used = row.times_used
        dto.avg_call_rating = float(row.avg_call_rating) if row.avg_call_rating is not None else None
        dto.created_by = row.created_by
        dto.notes = row.notes
        dto.created_at = row.created_at
        dto.activated_at = row.activated_at
        return dto

    @staticmethod
    def _abtest_from_row(row: Any) -> "ABTest":
        """Build an ABTest DTO from a PromptABTestRecord ORM row."""
        dto = ABTest.__new__(ABTest)
        dto.id = row.id
        dto.tenant_id = row.tenant_id
        dto.name = row.name
        dto.description = row.description
        dto.prompt_type = PromptType(row.prompt_type)
        dto.variant_a_id = row.variant_a_id
        dto.variant_b_id = row.variant_b_id
        dto.split_percentage = row.split_percentage
        dto.is_active = row.is_active
        dto.started_at = row.started_at
        dto.ended_at = row.ended_at
        dto.winning_variant = row.winning_variant
        dto.total_participants = row.total_participants
        dto.variant_a_calls = row.variant_a_calls
        dto.variant_b_calls = row.variant_b_calls
        dto.variant_a_avg_rating = float(row.variant_a_avg_rating) if row.variant_a_avg_rating is not None else None
        dto.variant_b_avg_rating = float(row.variant_b_avg_rating) if row.variant_b_avg_rating is not None else None
        return dto

    # -- Version Management -----------------------------------------------

    async def create_version(
        self,
        tenant_id: uuid.UUID,
        prompt_type: PromptType,
        name: str,
        content: str,
        variables: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
    ) -> PromptVersion:
        """Create a new prompt version.

        Version numbers are auto-incremented per tenant+type.
        """
        if self.session_maker is not None:
            from sqlalchemy import func, select

            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                max_stmt = select(func.max(PromptVersionRecord.version_number)).where(
                    PromptVersionRecord.tenant_id == tenant_id,
                    PromptVersionRecord.prompt_type == prompt_type.value,
                )
                current_max = (await session.execute(max_stmt)).scalar()
                version_number = (current_max or 0) + 1

                row = PromptVersionRecord(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    prompt_type=prompt_type.value,
                    version_number=version_number,
                    name=name,
                    content=content,
                    variables_json=variables or {},
                    status=PromptStatus.DRAFT.value,
                    is_active=False,
                    times_used=0,
                    created_by=created_by,
                    notes=notes,
                    created_at=datetime.utcnow(),
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
                logger.info(
                    "prompt.created",
                    version_id=str(row.id),
                    tenant_id=str(tenant_id),
                    prompt_type=prompt_type.value,
                    version_number=version_number,
                )
                return self._version_from_row(row)

        counter_key = f"{tenant_id}:{prompt_type.value}"
        if counter_key not in self._tenant_counters:
            self._tenant_counters[counter_key] = {"version": 0}

        self._tenant_counters[counter_key]["version"] += 1
        version_number = self._tenant_counters[counter_key]["version"]

        version = PromptVersion(
            tenant_id=tenant_id,
            prompt_type=prompt_type,
            version_number=version_number,
            name=name,
            content=content,
            variables=variables,
            created_by=created_by,
            notes=notes,
        )

        self._versions[str(version.id)] = version

        logger.info(
            "prompt.created",
            version_id=str(version.id),
            tenant_id=str(tenant_id),
            prompt_type=prompt_type.value,
            version_number=version_number,
        )

        return version

    async def get_version(self, version_id: uuid.UUID) -> Optional[PromptVersion]:
        """Get a prompt version by ID."""
        if self.session_maker is not None:
            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                row = await session.get(PromptVersionRecord, version_id)
                return self._version_from_row(row) if row else None
        return self._versions.get(str(version_id))

    async def list_versions(
        self,
        tenant_id: uuid.UUID,
        prompt_type: Optional[PromptType] = None,
        include_archived: bool = False,
    ) -> List[PromptVersion]:
        """List prompt versions for a tenant."""
        if self.session_maker is not None:
            from sqlalchemy import select

            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                stmt = select(PromptVersionRecord).where(
                    PromptVersionRecord.tenant_id == tenant_id
                )
                if prompt_type:
                    stmt = stmt.where(PromptVersionRecord.prompt_type == prompt_type.value)
                if not include_archived:
                    stmt = stmt.where(PromptVersionRecord.status != PromptStatus.ARCHIVED.value)
                stmt = stmt.order_by(PromptVersionRecord.created_at.desc())
                rows = (await session.execute(stmt)).scalars().all()
                return [self._version_from_row(r) for r in rows]

        versions = [
            v for v in self._versions.values()
            if v.tenant_id == tenant_id
        ]

        if prompt_type:
            versions = [v for v in versions if v.prompt_type == prompt_type]

        if not include_archived:
            versions = [v for v in versions if v.status != PromptStatus.ARCHIVED]

        return sorted(versions, key=lambda v: v.created_at, reverse=True)

    async def get_active_version(
        self, tenant_id: uuid.UUID, prompt_type: PromptType
    ) -> Optional[PromptVersion]:
        """Get the currently active prompt version for a tenant+type."""
        if self.session_maker is not None:
            from sqlalchemy import select

            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                stmt = select(PromptVersionRecord).where(
                    PromptVersionRecord.tenant_id == tenant_id,
                    PromptVersionRecord.prompt_type == prompt_type.value,
                    PromptVersionRecord.is_active.is_(True),
                )
                row = (await session.execute(stmt)).scalar_one_or_none()
                return self._version_from_row(row) if row else None

        for v in self._versions.values():
            if v.tenant_id == tenant_id and v.prompt_type == prompt_type and v.is_active:
                return v
        return None

    async def activate_version(self, version_id: uuid.UUID) -> PromptVersion:
        """Activate a prompt version.

        Deactivates any other active version for the same tenant+type.
        """
        if self.session_maker is not None:
            from sqlalchemy import select, update

            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                row = await session.get(PromptVersionRecord, version_id)
                if not row:
                    raise ValueError(f"Version {version_id} not found")

                # Deactivate + archive other active versions of same tenant+type
                await session.execute(
                    update(PromptVersionRecord)
                    .where(
                        PromptVersionRecord.tenant_id == row.tenant_id,
                        PromptVersionRecord.prompt_type == row.prompt_type,
                        PromptVersionRecord.id != row.id,
                        PromptVersionRecord.is_active.is_(True),
                    )
                    .values(is_active=False, status=PromptStatus.ARCHIVED.value)
                )

                row.is_active = True
                row.status = PromptStatus.ACTIVE.value
                row.activated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(row)
                logger.info(
                    "prompt.activated",
                    version_id=str(version_id),
                    tenant_id=str(row.tenant_id),
                    prompt_type=row.prompt_type,
                )
                return self._version_from_row(row)

        version = self._versions.get(str(version_id))
        if not version:
            raise ValueError(f"Version {version_id} not found")

        # Deactivate other versions for same tenant+type
        for v in self._versions.values():
            if (
                v.tenant_id == version.tenant_id
                and v.prompt_type == version.prompt_type
                and v.id != version.id
                and v.is_active
            ):
                v.is_active = False
                v.status = PromptStatus.ARCHIVED

        version.is_active = True
        version.status = PromptStatus.ACTIVE
        version.activated_at = datetime.utcnow()

        logger.info(
            "prompt.activated",
            version_id=str(version_id),
            tenant_id=str(version.tenant_id),
            prompt_type=version.prompt_type.value,
        )

        return version

    async def archive_version(self, version_id: uuid.UUID) -> PromptVersion:
        """Archive a prompt version."""
        if self.session_maker is not None:
            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                row = await session.get(PromptVersionRecord, version_id)
                if not row:
                    raise ValueError(f"Version {version_id} not found")
                row.status = PromptStatus.ARCHIVED.value
                row.is_active = False
                await session.commit()
                await session.refresh(row)
                logger.info("prompt.archived", version_id=str(version_id))
                return self._version_from_row(row)

        version = self._versions.get(str(version_id))
        if not version:
            raise ValueError(f"Version {version_id} not found")

        version.status = PromptStatus.ARCHIVED
        version.is_active = False

        logger.info("prompt.archived", version_id=str(version_id))
        return version

    # -- A/B Testing ------------------------------------------------------

    async def create_ab_test(
        self,
        tenant_id: uuid.UUID,
        name: str,
        prompt_type: PromptType,
        variant_a_id: uuid.UUID,
        variant_b_id: uuid.UUID,
        split_percentage: int = 50,
        description: Optional[str] = None,
    ) -> ABTest:
        """Create a new A/B test.

        Args:
            tenant_id: Tenant ID
            name: Test name
            prompt_type: Type of prompt being tested
            variant_a_id: First variant prompt version ID
            variant_b_id: Second variant prompt version ID
            split_percentage: Percentage of traffic to variant B (0-100)
            description: Optional description
        """
        if self.session_maker is not None:
            from backend.db.models.prompts import (
                PromptABTestRecord,
                PromptVersionRecord,
            )

            async with self.session_maker() as session:
                v_a = await session.get(PromptVersionRecord, variant_a_id)
                v_b = await session.get(PromptVersionRecord, variant_b_id)
                if not v_a or not v_b:
                    raise ValueError("One or both variant versions not found")

                test_row = PromptABTestRecord(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    name=name,
                    description=description,
                    prompt_type=prompt_type.value,
                    variant_a_id=variant_a_id,
                    variant_b_id=variant_b_id,
                    split_percentage=split_percentage,
                    is_active=True,
                    started_at=datetime.utcnow(),
                )
                session.add(test_row)

                v_a.status = PromptStatus.AB_TEST.value
                v_a.ab_test_id = test_row.id
                v_a.ab_test_group = "A"
                v_b.status = PromptStatus.AB_TEST.value
                v_b.ab_test_id = test_row.id
                v_b.ab_test_group = "B"

                await session.commit()
                await session.refresh(test_row)
                logger.info(
                    "abtest.created",
                    test_id=str(test_row.id),
                    tenant_id=str(tenant_id),
                    name=name,
                    split=split_percentage,
                )
                return self._abtest_from_row(test_row)

        # Validate versions exist
        v_a = self._versions.get(str(variant_a_id))
        v_b = self._versions.get(str(variant_b_id))
        if not v_a or not v_b:
            raise ValueError("One or both variant versions not found")

        ab_test = ABTest(
            tenant_id=tenant_id,
            name=name,
            prompt_type=prompt_type,
            variant_a_id=variant_a_id,
            variant_b_id=variant_b_id,
            split_percentage=split_percentage,
            description=description,
        )

        # Mark versions as AB test
        if v_a:
            v_a.status = PromptStatus.AB_TEST
            v_a.ab_test_id = ab_test.id
            v_a.ab_test_group = "A"
        if v_b:
            v_b.status = PromptStatus.AB_TEST
            v_b.ab_test_id = ab_test.id
            v_b.ab_test_group = "B"

        self._ab_tests[str(ab_test.id)] = ab_test

        logger.info(
            "abtest.created",
            test_id=str(ab_test.id),
            tenant_id=str(tenant_id),
            name=name,
            split=split_percentage,
        )

        return ab_test

    async def get_ab_test(self, test_id: uuid.UUID) -> Optional[ABTest]:
        """Get an A/B test by ID."""
        if self.session_maker is not None:
            from backend.db.models.prompts import PromptABTestRecord

            async with self.session_maker() as session:
                row = await session.get(PromptABTestRecord, test_id)
                return self._abtest_from_row(row) if row else None
        return self._ab_tests.get(str(test_id))

    async def list_ab_tests(
        self, tenant_id: uuid.UUID, active_only: bool = False
    ) -> List[ABTest]:
        """List A/B tests for a tenant."""
        if self.session_maker is not None:
            from sqlalchemy import select

            from backend.db.models.prompts import PromptABTestRecord

            async with self.session_maker() as session:
                stmt = select(PromptABTestRecord).where(
                    PromptABTestRecord.tenant_id == tenant_id
                )
                if active_only:
                    stmt = stmt.where(PromptABTestRecord.is_active.is_(True))
                stmt = stmt.order_by(PromptABTestRecord.started_at.desc())
                rows = (await session.execute(stmt)).scalars().all()
                return [self._abtest_from_row(r) for r in rows]

        tests = [
            t for t in self._ab_tests.values()
            if t.tenant_id == tenant_id
        ]
        if active_only:
            tests = [t for t in tests if t.is_active]
        return sorted(tests, key=lambda t: t.started_at, reverse=True)

    async def end_ab_test(
        self,
        test_id: uuid.UUID,
        winning_variant: Optional[str] = None,
    ) -> ABTest:
        """End an A/B test.

        Args:
            test_id: The A/B test ID
            winning_variant: "A" or "B" (or None for inconclusive)
        """
        if self.session_maker is not None:
            from backend.db.models.prompts import PromptABTestRecord

            async with self.session_maker() as session:
                row = await session.get(PromptABTestRecord, test_id)
                if not row:
                    raise ValueError(f"A/B test {test_id} not found")
                row.is_active = False
                row.ended_at = datetime.utcnow()
                row.winning_variant = winning_variant
                await session.commit()
                await session.refresh(row)
                dto = self._abtest_from_row(row)

            # Activate winner / archive loser via the (DB-aware) version methods
            if winning_variant:
                winner_id = dto.variant_a_id if winning_variant == "A" else dto.variant_b_id
                loser_id = dto.variant_b_id if winning_variant == "A" else dto.variant_a_id
                await self.activate_version(winner_id)
                await self.archive_version(loser_id)

            logger.info(
                "abtest.ended",
                test_id=str(test_id),
                winner=winning_variant,
                participants=dto.total_participants,
            )
            return dto

        ab_test = self._ab_tests.get(str(test_id))
        if not ab_test:
            raise ValueError(f"A/B test {test_id} not found")

        ab_test.is_active = False
        ab_test.ended_at = datetime.utcnow()
        ab_test.winning_variant = winning_variant

        # Activate winning variant, archive losing
        if winning_variant:
            variant_id = (
                ab_test.variant_a_id if winning_variant == "A"
                else ab_test.variant_b_id
            )
            await self.activate_version(variant_id)

            # Archive the losing variant
            loser_id = (
                ab_test.variant_b_id if winning_variant == "A"
                else ab_test.variant_a_id
            )
            await self.archive_version(loser_id)

        logger.info(
            "abtest.ended",
            test_id=str(test_id),
            winner=winning_variant,
            participants=ab_test.total_participants,
        )

        return ab_test

    async def record_call_for_ab_test(
        self,
        test_id: uuid.UUID,
        variant: str,
        rating: Optional[float] = None,
    ) -> None:
        """Record a call result for an A/B test."""
        if self.session_maker is not None:
            from backend.db.models.prompts import PromptABTestRecord

            async with self.session_maker() as session:
                row = await session.get(PromptABTestRecord, test_id)
                if not row:
                    return
                row.total_participants += 1
                if variant == "A":
                    row.variant_a_calls += 1
                    row.variant_a_avg_rating = self._running_avg(
                        row.variant_a_avg_rating, row.variant_a_calls, rating
                    )
                elif variant == "B":
                    row.variant_b_calls += 1
                    row.variant_b_avg_rating = self._running_avg(
                        row.variant_b_avg_rating, row.variant_b_calls, rating
                    )
                await session.commit()
            return

        ab_test = self._ab_tests.get(str(test_id))
        if not ab_test:
            return

        ab_test.total_participants += 1
        if variant == "A":
            ab_test.variant_a_calls += 1
            if rating is not None:
                if ab_test.variant_a_avg_rating is None:
                    ab_test.variant_a_avg_rating = rating
                else:
                    ab_test.variant_a_avg_rating = (
                        (ab_test.variant_a_avg_rating * (ab_test.variant_a_calls - 1) + rating)
                        / ab_test.variant_a_calls
                    )
        elif variant == "B":
            ab_test.variant_b_calls += 1
            if rating is not None:
                if ab_test.variant_b_avg_rating is None:
                    ab_test.variant_b_avg_rating = rating
                else:
                    ab_test.variant_b_avg_rating = (
                        (ab_test.variant_b_avg_rating * (ab_test.variant_b_calls - 1) + rating)
                        / ab_test.variant_b_calls
                    )

    @staticmethod
    def _running_avg(
        current: Optional[Decimal], new_count: int, rating: Optional[float]
    ) -> Optional[Decimal]:
        """Incrementally update a running average rating (DB-stored Decimal)."""
        if rating is None:
            return current
        if current is None or new_count <= 1:
            return Decimal(str(rating))
        prev = float(current)
        updated = (prev * (new_count - 1) + rating) / new_count
        return Decimal(str(round(updated, 3)))

    async def select_variant_for_call(
        self, test_id: uuid.UUID
    ) -> Optional[str]:
        """Select A or B variant for an incoming call based on split."""
        import random

        ab_test = await self.get_ab_test(test_id)
        if not ab_test or not ab_test.is_active:
            return None

        r = random.randint(1, 100)
        return "B" if r <= ab_test.split_percentage else "A"

    # -- Default Prompts --------------------------------------------------

    async def get_default_prompt(
        self, prompt_type: PromptType
    ) -> str:
        """Get default prompt content for a given type."""
        defaults: Dict[PromptType, str] = {
            PromptType.SYSTEM: (
                "You are the AI phone assistant for {business_name}. "
                "You are professional, friendly, and helpful. "
                "Answer questions about the business, take messages, "
                "and schedule appointments. Be concise and natural."
            ),
            PromptType.GREETING: (
                "Hello, thank you for calling {business_name}. "
                "This is your AI assistant. How may I help you today?"
            ),
            PromptType.HOLD: (
                "Please hold while I check that for you. "
                "I'll be right back."
            ),
            PromptType.VOICEMAIL: (
                "We're not available right now. Please leave your name, "
                "phone number, and a brief message after the tone."
            ),
            PromptType.TRANSFER: (
                "I'll transfer you now. Please hold the line."
            ),
            PromptType.GOODBYE: (
                "Thank you for calling {business_name}. Have a great day!"
            ),
            PromptType.FALLBACK: (
                "I'm sorry, I didn't quite understand that. "
                "Could you please rephrase? Or I can take a message "
                "for the team to follow up with you."
            ),
        }

        return defaults.get(prompt_type, "")

    async def create_default_versions(
        self, tenant_id: uuid.UUID, created_by: Optional[uuid.UUID] = None
    ) -> List[PromptVersion]:
        """Create default prompt versions for a new tenant."""
        versions = []
        for prompt_type in [
            PromptType.SYSTEM,
            PromptType.GREETING,
            PromptType.HOLD,
            PromptType.VOICEMAIL,
            PromptType.TRANSFER,
            PromptType.GOODBYE,
            PromptType.FALLBACK,
        ]:
            content = await self.get_default_prompt(prompt_type)
            version = await self.create_version(
                tenant_id=tenant_id,
                prompt_type=prompt_type,
                name=f"Default {prompt_type.value.title()}",
                content=content,
                variables={"business_name": "placeholder"},
                created_by=created_by,
                notes="Auto-generated default prompt",
            )
            versions.append(version)

        # Activate system prompt
        system_version = versions[0]
        await self.activate_version(system_version.id)

        logger.info(
            "prompt.defaults_created",
            tenant_id=str(tenant_id),
            count=len(versions),
        )

        return versions

    # -- Performance Tracking ---------------------------------------------

    async def record_usage(self, version_id: uuid.UUID, rating: Optional[float] = None) -> None:
        """Record usage and optional rating for a prompt version."""
        if self.session_maker is not None:
            from backend.db.models.prompts import PromptVersionRecord

            async with self.session_maker() as session:
                row = await session.get(PromptVersionRecord, version_id)
                if not row:
                    return
                row.times_used += 1
                row.avg_call_rating = self._running_avg(
                    row.avg_call_rating, row.times_used, rating
                )
                await session.commit()
            return

        version = self._versions.get(str(version_id))
        if not version:
            return

        version.times_used += 1

        if rating is not None:
            if version.avg_call_rating is None:
                version.avg_call_rating = rating
            else:
                version.avg_call_rating = (
                    (version.avg_call_rating * (version.times_used - 1) + rating)
                    / version.times_used
                )

    async def get_prompt_performance(
        self, tenant_id: uuid.UUID, prompt_type: Optional[PromptType] = None
    ) -> List[Dict[str, Any]]:
        """Get performance metrics for prompt versions."""
        versions = await self.list_versions(tenant_id, prompt_type, include_archived=True)

        return [
            {
                "version_id": str(v.id),
                "version_number": v.version_number,
                "name": v.name,
                "status": v.status.value,
                "is_active": v.is_active,
                "times_used": v.times_used,
                "avg_call_rating": v.avg_call_rating,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]
