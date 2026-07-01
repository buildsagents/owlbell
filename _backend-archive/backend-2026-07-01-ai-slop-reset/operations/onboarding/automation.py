"""operations/onboarding/automation.py - Automated onboarding pipeline.

Handles the post-sale onboarding sequence for new clients:
- Onboarding checklist creation and tracking
- Automated task triggers on step completion
- Email sequence for onboarding progress
- Webhook notifications for agency dashboard
- Integration provisioning (calendar, CRM, phone)

Design:
- Each client gets an OnboardingPipeline with defined steps
- Completing a step triggers automated actions
- The agency dashboard polls or subscribes to pipeline status
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class OnboardingStep:
    """A single step in the onboarding pipeline."""

    def __init__(
        self,
        step_id: str,
        name: str,
        description: str,
        order: int,
        auto_completes: bool = False,
        requires_action: bool = False,
        estimated_days: int = 1,
    ):
        self.step_id = step_id
        self.name = name
        self.description = description
        self.order = order
        self.auto_completes = auto_completes
        self.requires_action = requires_action
        self.estimated_days = estimated_days
        self.status = StepStatus.PENDING
        self.completed_at: Optional[datetime] = None
        self.notes: Optional[str] = None
        self.assignee: Optional[str] = None

    def complete(self, notes: Optional[str] = None) -> None:
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if notes:
            self.notes = notes

    def start(self, assignee: Optional[str] = None) -> None:
        self.status = StepStatus.IN_PROGRESS
        if assignee:
            self.assignee = assignee

    def block(self, reason: str) -> None:
        self.status = StepStatus.BLOCKED
        self.notes = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "status": self.status.value,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
            "assignee": self.assignee,
            "estimated_days": self.estimated_days,
        }


# ---------------------------------------------------------------------------
# Default onboarding pipeline definition
# ---------------------------------------------------------------------------

DEFAULT_PIPELINE_STEPS = [
    {
        "step_id": "welcome_email",
        "name": "Welcome email sent",
        "description": "Send welcome email with onboarding link and next steps",
        "order": 1,
        "auto_completes": True,
        "estimated_days": 0,
    },
    {
        "step_id": "intake_form",
        "name": "Intake form submitted",
        "description": "Client fills out business info: hours, services, FAQs, greeting preferences",
        "order": 2,
        "requires_action": True,
        "estimated_days": 1,
    },
    {
        "step_id": "ai_configuration",
        "name": "AI configured",
        "description": "System prompt, greeting, and knowledge base built from intake form",
        "order": 3,
        "auto_completes": True,
        "estimated_days": 0,
    },
    {
        "step_id": "phone_setup",
        "name": "Phone number provisioned",
        "description": "Retell number provisioned or forwarding configured",
        "order": 4,
        "auto_completes": True,
        "estimated_days": 0,
    },
    {
        "step_id": "calendar_integration",
        "name": "Calendar connected",
        "description": "Google Calendar / CRM integration linked and verified",
        "order": 5,
        "requires_action": True,
        "estimated_days": 1,
    },
    {
        "step_id": "test_calls",
        "name": "Test calls completed",
        "description": "Internal test calls to verify greeting, booking, and routing",
        "order": 6,
        "auto_completes": True,
        "estimated_days": 0,
    },
    {
        "step_id": "client_approval",
        "name": "Client approved",
        "description": "Client confirms greeting and behavior via test call or dashboard review",
        "order": 7,
        "requires_action": True,
        "estimated_days": 1,
    },
    {
        "step_id": "go_live",
        "name": "Go live",
        "description": "Calls routed to Owlbell, monitoring active",
        "order": 8,
        "auto_completes": True,
        "estimated_days": 0,
    },
    {
        "step_id": "day_1_check",
        "name": "Day 1 check-in",
        "description": "Automated check-in email after first 24 hours live",
        "order": 9,
        "auto_completes": True,
        "estimated_days": 1,
    },
    {
        "step_id": "week_1_review",
        "name": "Week 1 review",
        "description": "Success specialist emails week-1 metrics summary and script recommendations",
        "order": 10,
        "requires_action": True,
        "estimated_days": 7,
    },
]


# ---------------------------------------------------------------------------
# Onboarding Pipeline
# ---------------------------------------------------------------------------

class OnboardingPipeline:
    """Tracks the onboarding progress for a single client tenant."""

    def __init__(
        self,
        tenant_id: str,
        tenant_name: str,
        tenant_email: str,
        steps: Optional[list[dict]] = None,
        pipeline_id: Optional[str] = None,
    ):
        self.id = pipeline_id
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.tenant_email = tenant_email
        self.created_at = datetime.utcnow()
        self.steps: list[OnboardingStep] = []
        self._callbacks: list[Callable] = []

        step_defs = steps or DEFAULT_PIPELINE_STEPS
        for step_def in step_defs:
            self.steps.append(OnboardingStep(**step_def))

    @property
    def current_step(self) -> Optional[OnboardingStep]:
        """Get the first non-completed step."""
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS, StepStatus.BLOCKED):
                return step
        return None

    @property
    def progress_percent(self) -> float:
        """Completion percentage."""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return round((completed / max(len(self.steps), 1)) * 100, 1)

    @property
    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    @property
    def current_step_index(self) -> int:
        for i, step in enumerate(self.steps):
            if step.status != StepStatus.COMPLETED:
                return i
        return len(self.steps)

    def complete_step(self, step_id: str, notes: Optional[str] = None) -> dict[str, Any]:
        """Mark a step as complete and trigger post-completion actions."""
        step = None
        for s in self.steps:
            if s.step_id == step_id:
                step = s
                break

        if not step:
            return {"success": False, "error": f"Step '{step_id}' not found"}

        if step.status == StepStatus.COMPLETED:
            return {"success": True, "message": "Step already completed"}

        step.complete(notes)

        logger.info(
            "onboarding.step_completed",
            tenant_id=self.tenant_id,
            step_id=step_id,
            progress=self.progress_percent,
        )

        # Trigger post-completion actions
        actions = self._trigger_post_completion(step)

        return {
            "success": True,
            "step_id": step_id,
            "progress_percent": self.progress_percent,
            "is_complete": self.is_complete,
            "next_step": self.current_step.to_dict() if self.current_step else None,
            "actions_triggered": actions,
        }

    def start_step(self, step_id: str, assignee: Optional[str] = None) -> dict[str, Any]:
        """Mark a step as in progress."""
        for s in self.steps:
            if s.step_id == step_id:
                s.start(assignee)
                return {"success": True, "step_id": step_id, "status": "in_progress"}
        return {"success": False, "error": f"Step '{step_id}' not found"}

    def block_step(self, step_id: str, reason: str) -> dict[str, Any]:
        """Mark a step as blocked."""
        for s in self.steps:
            if s.step_id == step_id:
                s.block(reason)
                return {"success": True, "step_id": step_id, "status": "blocked"}
        return {"success": False, "error": f"Step '{step_id}' not found"}

    def get_status(self) -> dict[str, Any]:
        """Get full pipeline status."""
        return {
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant_name,
            "created_at": self.created_at.isoformat(),
            "progress_percent": self.progress_percent,
            "is_complete": self.is_complete,
            "current_step_index": self.current_step_index,
            "total_steps": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
        }

    def _trigger_post_completion(self, step: OnboardingStep) -> list[str]:
        """Trigger automated actions after a step completes."""
        actions = []

        # Auto-advance pending steps that depend on this one
        if step.step_id == "intake_form":
            # After intake form, auto-start AI configuration
            actions.append("trigger_ai_configuration")
            actions.append("send_intake_confirmation_email")

        elif step.step_id == "ai_configuration":
            # After AI is configured, auto-start phone setup
            actions.append("trigger_phone_setup")

        elif step.step_id == "phone_setup":
            # After phone is ready, send test instructions
            actions.append("send_test_instructions_email")

        elif step.step_id == "client_approval":
            # After client approves, go live
            actions.append("trigger_go_live")

        elif step.step_id == "go_live":
            # After going live, schedule day-1 check-in
            actions.append("schedule_day_1_checkin")
            actions.append("send_go_live_notification")

        elif step.step_id == "week_1_review":
            # After week 1 review, send satisfaction survey
            actions.append("send_satisfaction_survey")
            actions.append("notify_agency_dashboard")

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self.tenant_id, step.step_id, actions)
            except Exception as exc:
                logger.warning("onboarding.callback_failed", error=str(exc))

        return actions

    def on_step_complete(self, callback: Callable) -> None:
        """Register a callback for step completion events."""
        self._callbacks.append(callback)


# ---------------------------------------------------------------------------
# Email sequence for onboarding
# ---------------------------------------------------------------------------

ONBOARDING_EMAILS = [
    {
        "trigger": "welcome_email",
        "subject": "Welcome to Owlbell! Let's get you set up",
        "template": "onboarding_welcome",
        "delay_hours": 0,
    },
    {
        "trigger": "intake_form",
        "subject": "Quick question: your business hours & services",
        "template": "onboarding_intake_reminder",
        "delay_hours": 24,
    },
    {
        "trigger": "test_calls",
        "subject": "Your Owlbell is ready! Let's test it",
        "template": "onboarding_test_calls",
        "delay_hours": 0,
    },
    {
        "trigger": "go_live",
        "subject": "You're live! Here's what to expect",
        "template": "onboarding_go_live",
        "delay_hours": 0,
    },
    {
        "trigger": "day_1_check",
        "subject": "How's your first day going?",
        "template": "onboarding_day1_checkin",
        "delay_hours": 24,
    },
    {
        "trigger": "week_1_review",
        "subject": "Your first week results are in",
        "template": "onboarding_week1_review",
        "delay_hours": 0,
    },
]


def get_pending_emails(pipeline: OnboardingPipeline) -> list[dict[str, Any]]:
    """Determine which onboarding emails should be sent based on pipeline status."""
    pending = []
    completed_step_ids = {s.step_id for s in pipeline.steps if s.status == StepStatus.COMPLETED}

    for email_def in ONBOARDING_EMAILS:
        trigger_step = email_def["trigger"]
        if trigger_step in completed_step_ids:
            # Check if this email was already sent (track in production)
            pending.append({
                "trigger": trigger_step,
                "subject": email_def["subject"],
                "template": email_def["template"],
                "recipient": pipeline.tenant_email,
                "tenant_id": pipeline.tenant_id,
            })

    return pending


# ---------------------------------------------------------------------------
# Pipeline storage (DB-backed via onboarding_pipelines / onboarding_steps)
# ---------------------------------------------------------------------------


def _hydrate_pipeline(prow: Any) -> OnboardingPipeline:
    """Build an OnboardingPipeline domain object from ORM rows."""
    pipeline = OnboardingPipeline(
        tenant_id=str(prow.tenant_id),
        tenant_name=prow.tenant_name,
        tenant_email=prow.tenant_email,
        steps=[],  # replaced below from persisted step rows
        pipeline_id=str(prow.id),
    )
    pipeline.created_at = prow.created_at
    pipeline.steps = []
    for srow in sorted(prow.steps, key=lambda s: s.step_order):
        step = OnboardingStep(
            step_id=srow.step_id,
            name=srow.name,
            description=srow.description,
            order=srow.step_order,
            auto_completes=srow.auto_completes,
            requires_action=srow.requires_action,
            estimated_days=srow.estimated_days,
        )
        step.status = StepStatus(srow.status)
        step.completed_at = srow.completed_at
        step.notes = srow.notes
        step.assignee = srow.assignee
        pipeline.steps.append(step)
    return pipeline


async def get_pipeline(session_maker: Callable[[], Any], tenant_id: str) -> Optional[OnboardingPipeline]:
    """Get the onboarding pipeline for a tenant (or None)."""
    from sqlalchemy import select

    from backend.db.models.onboarding import OnboardingPipelineRecord

    async with session_maker() as session:
        stmt = select(OnboardingPipelineRecord).where(
            OnboardingPipelineRecord.tenant_id == UUID(str(tenant_id))
        )
        prow = (await session.execute(stmt)).scalar_one_or_none()
        return _hydrate_pipeline(prow) if prow else None


async def create_pipeline(
    session_maker: Callable[[], Any],
    tenant_id: str,
    tenant_name: str,
    tenant_email: str,
    steps: Optional[list[dict]] = None,
) -> OnboardingPipeline:
    """Create and persist a new onboarding pipeline for a tenant.

    Idempotent: if a pipeline already exists for the tenant it is returned
    unchanged rather than duplicated.
    """
    from sqlalchemy import select

    from backend.db.models.onboarding import (
        OnboardingPipelineRecord,
        OnboardingStepRecord,
    )

    existing = await get_pipeline(session_maker, tenant_id)
    if existing is not None:
        return existing

    domain = OnboardingPipeline(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        tenant_email=tenant_email,
        steps=steps,
    )

    async with session_maker() as session:
        prow = OnboardingPipelineRecord(
            id=uuid4(),
            tenant_id=UUID(str(tenant_id)),
            tenant_name=tenant_name,
            tenant_email=tenant_email,
            created_at=domain.created_at,
        )
        session.add(prow)
        for step in domain.steps:
            session.add(OnboardingStepRecord(
                id=uuid4(),
                pipeline_id=prow.id,
                tenant_id=UUID(str(tenant_id)),
                step_id=step.step_id,
                name=step.name,
                description=step.description,
                step_order=step.order,
                auto_completes=step.auto_completes,
                requires_action=step.requires_action,
                estimated_days=step.estimated_days,
                status=step.status.value,
            ))
        await session.commit()
        domain.id = str(prow.id)

    logger.info("onboarding.pipeline_created", tenant_id=str(tenant_id), steps=len(domain.steps))
    return domain


async def _persist_step(
    session_maker: Callable[[], Any], pipeline: OnboardingPipeline, step_id: str
) -> None:
    """Write a single step's mutated state back to the database."""
    from sqlalchemy import select

    from backend.db.models.onboarding import OnboardingStepRecord

    step = next((s for s in pipeline.steps if s.step_id == step_id), None)
    if step is None or pipeline.id is None:
        return
    async with session_maker() as session:
        stmt = select(OnboardingStepRecord).where(
            OnboardingStepRecord.pipeline_id == UUID(str(pipeline.id)),
            OnboardingStepRecord.step_id == step_id,
        )
        srow = (await session.execute(stmt)).scalar_one_or_none()
        if srow is None:
            return
        srow.status = step.status.value
        srow.completed_at = step.completed_at
        srow.notes = step.notes
        srow.assignee = step.assignee
        await session.commit()


async def complete_step(
    session_maker: Callable[[], Any], tenant_id: str, step_id: str, notes: Optional[str] = None
) -> dict[str, Any]:
    """Complete a pipeline step and persist the change."""
    pipeline = await get_pipeline(session_maker, tenant_id)
    if pipeline is None:
        return {"success": False, "error": "Pipeline not found"}
    result = pipeline.complete_step(step_id, notes)
    if result.get("success"):
        await _persist_step(session_maker, pipeline, step_id)
    return result


async def start_step(
    session_maker: Callable[[], Any], tenant_id: str, step_id: str, assignee: Optional[str] = None
) -> dict[str, Any]:
    """Mark a step in progress and persist the change."""
    pipeline = await get_pipeline(session_maker, tenant_id)
    if pipeline is None:
        return {"success": False, "error": "Pipeline not found"}
    result = pipeline.start_step(step_id, assignee)
    if result.get("success"):
        await _persist_step(session_maker, pipeline, step_id)
    return result


async def block_step(
    session_maker: Callable[[], Any], tenant_id: str, step_id: str, reason: str
) -> dict[str, Any]:
    """Mark a step blocked and persist the change."""
    pipeline = await get_pipeline(session_maker, tenant_id)
    if pipeline is None:
        return {"success": False, "error": "Pipeline not found"}
    result = pipeline.block_step(step_id, reason)
    if result.get("success"):
        await _persist_step(session_maker, pipeline, step_id)
    return result


async def list_pipelines(session_maker: Callable[[], Any]) -> list[dict[str, Any]]:
    """List all onboarding pipelines with their status."""
    from sqlalchemy import select

    from backend.db.models.onboarding import OnboardingPipelineRecord

    async with session_maker() as session:
        stmt = select(OnboardingPipelineRecord).order_by(
            OnboardingPipelineRecord.created_at.desc()
        )
        prows = (await session.execute(stmt)).scalars().all()
        return [_hydrate_pipeline(p).get_status() for p in prows]
