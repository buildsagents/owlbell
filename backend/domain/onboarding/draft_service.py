"""Resumable onboarding drafts — server-backed for multi-device resume."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from backend.domain.onboarding.intake_service import IntakeDatabaseError, _require_session_maker

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DraftResult:
    draft_id: str
    email: str
    step: int
    payload: dict[str, Any]
    updated_at: str


def _new_token() -> str:
    return secrets.token_urlsafe(24)


async def save_draft(
    *,
    email: str,
    payload: dict[str, Any],
    step: int = 0,
    draft_id: Optional[str] = None,
) -> DraftResult:
    from backend.db.models.onboarding import OnboardingIntakeRecord

    email_norm = email.strip().lower()
    if not email_norm:
        raise ValueError("email_required")

    token = draft_id or _new_token()
    body = {
        **payload,
        "draft_token": token,
        "step": step,
        "draft_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        sm = _require_session_maker()
        async with sm() as db:
            record = None
            if draft_id:
                try:
                    record = await db.get(OnboardingIntakeRecord, UUID(draft_id))
                except ValueError:
                    record = None
                if record and record.status != "draft":
                    record = None

            if record is None:
                record = OnboardingIntakeRecord(
                    email=email_norm,
                    business_name=str(payload.get("businessName") or payload.get("business_name") or "Draft"),
                    payload_json=body,
                    status="draft",
                )
                db.add(record)
            else:
                record.payload_json = body
                record.email = email_norm
                if payload.get("businessName"):
                    record.business_name = str(payload["businessName"])

            await db.commit()
            await db.refresh(record)
            return DraftResult(
                draft_id=str(record.id),
                email=email_norm,
                step=step,
                payload=body,
                updated_at=body["draft_updated_at"],
            )
    except IntakeDatabaseError:
        raise
    except Exception as exc:
        raise IntakeDatabaseError(str(exc)) from exc


async def load_draft(*, draft_id: str) -> Optional[DraftResult]:
    from backend.db.models.onboarding import OnboardingIntakeRecord

    try:
        sm = _require_session_maker()
        async with sm() as db:
            record = await db.get(OnboardingIntakeRecord, UUID(draft_id))
            if not record or record.status != "draft":
                return None
            payload = dict(record.payload_json or {})
            return DraftResult(
                draft_id=str(record.id),
                email=record.email,
                step=int(payload.get("step", 0)),
                payload=payload,
                updated_at=str(payload.get("draft_updated_at") or ""),
            )
    except Exception as exc:
        logger.warning("onboarding.load_draft_failed", error=str(exc))
        return None


async def load_draft_by_email(email: str) -> Optional[DraftResult]:
    from sqlalchemy import func, select

    from backend.db.models.onboarding import OnboardingIntakeRecord

    email_norm = email.strip().lower()
    try:
        sm = _require_session_maker()
        async with sm() as db:
            row = await db.execute(
                select(OnboardingIntakeRecord)
                .where(
                    func.lower(OnboardingIntakeRecord.email) == email_norm,
                    OnboardingIntakeRecord.status == "draft",
                )
                .order_by(OnboardingIntakeRecord.created_at.desc())
                .limit(1)
            )
            record = row.scalar_one_or_none()
            if not record:
                return None
            payload = dict(record.payload_json or {})
            return DraftResult(
                draft_id=str(record.id),
                email=record.email,
                step=int(payload.get("step", 0)),
                payload=payload,
                updated_at=str(payload.get("draft_updated_at") or ""),
            )
    except Exception as exc:
        logger.warning("onboarding.load_draft_by_email_failed", error=str(exc))
        return None