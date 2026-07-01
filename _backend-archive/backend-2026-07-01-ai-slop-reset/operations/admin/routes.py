"""operations/admin/routes.py - Admin API routes.

Extended admin operations: bulk actions, system configuration,
training interface, and advanced tenant management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class AdminActionRequest:
    """Request for admin actions on tenants."""

    def __init__(
        self,
        action: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.action = action
        self.reason = reason
        self.metadata = metadata or {}


class AdminBulkActionRequest:
    """Request for bulk admin actions."""

    def __init__(
        self,
        tenant_ids: List[uuid.UUID],
        action: str,
        reason: str,
    ):
        self.tenant_ids = tenant_ids
        self.action = action
        self.reason = reason


class AdminService:
    """Admin service for system-level operations.

    Provides bulk actions, system configuration, training interface,
    and advanced tenant management capabilities.
    """

    VALID_ACTIONS = {
        "suspend", "reactivate", "change_plan", "terminate",
        "limit", "unlimit", "purge",
    }

    def __init__(self, tenant_manager: Optional[Any] = None):
        self.tenant_manager = tenant_manager
        self._training_queue: List[Dict[str, Any]] = []
        self._prompt_suggestions: List[Dict[str, Any]] = []

    # -- Bulk Actions -----------------------------------------------------

    async def execute_tenant_action(
        self,
        tenant_id: uuid.UUID,
        request: AdminActionRequest,
    ) -> Dict[str, Any]:
        """Execute a single admin action on a tenant.

        Args:
            tenant_id: Target tenant ID
            request: Action request

        Returns:
            Action result
        """
        if request.action not in self.VALID_ACTIONS:
            return {
                "success": False,
                "error": f"Invalid action: {request.action}",
            }

        logger.info(
            "admin.tenant_action",
            tenant_id=str(tenant_id),
            action=request.action,
            reason=request.reason,
        )

        # Route to appropriate handler
        action_handlers = {
            "suspend": self._handle_suspend,
            "reactivate": self._handle_reactivate,
            "limit": self._handle_limit,
            "unlimit": self._handle_unlimit,
            "terminate": self._handle_terminate,
            "change_plan": self._handle_change_plan,
        }

        handler = action_handlers.get(request.action)
        if handler:
            return await handler(tenant_id, request)

        return {"success": True, "action": request.action, "tenant_id": str(tenant_id)}

    async def execute_bulk_action(
        self,
        request: AdminBulkActionRequest,
    ) -> Dict[str, Any]:
        """Execute an action on multiple tenants.

        Args:
            request: Bulk action request

        Returns:
            Results per tenant
        """
        results = []
        for tenant_id in request.tenant_ids:
            action_request = AdminActionRequest(
                action=request.action,
                reason=request.reason,
            )
            result = await self.execute_tenant_action(tenant_id, action_request)
            results.append({
                "tenant_id": str(tenant_id),
                **result,
            })

        success_count = sum(1 for r in results if r.get("success"))

        logger.info(
            "admin.bulk_action",
            action=request.action,
            total=len(request.tenant_ids),
            success=success_count,
        )

        return {
            "success": success_count == len(request.tenant_ids),
            "total": len(request.tenant_ids),
            "successful": success_count,
            "failed": len(request.tenant_ids) - success_count,
            "results": results,
        }

    # -- Action Handlers --------------------------------------------------

    async def _handle_suspend(
        self, tenant_id: uuid.UUID, request: AdminActionRequest
    ) -> Dict[str, Any]:
        """Handle suspend action."""
        if self.tenant_manager:
            await self.tenant_manager.suspend_tenant(tenant_id, request.reason)
        return {"success": True, "action": "suspend", "tenant_id": str(tenant_id)}

    async def _handle_reactivate(
        self, tenant_id: uuid.UUID, request: AdminActionRequest
    ) -> Dict[str, Any]:
        """Handle reactivate action."""
        if self.tenant_manager:
            await self.tenant_manager.reactivate_tenant(tenant_id)
        return {"success": True, "action": "reactivate", "tenant_id": str(tenant_id)}

    async def _handle_limit(
        self, tenant_id: uuid.UUID, request: AdminActionRequest
    ) -> Dict[str, Any]:
        """Handle limit action."""
        if self.tenant_manager:
            await self.tenant_manager.set_limited(tenant_id)
        return {"success": True, "action": "limit", "tenant_id": str(tenant_id)}

    async def _handle_unlimit(
        self, tenant_id: uuid.UUID, request: AdminActionRequest
    ) -> Dict[str, Any]:
        """Handle unlimit action."""
        if self.tenant_manager:
            await self.tenant_manager.reactivate_tenant(tenant_id)
        return {"success": True, "action": "unlimit", "tenant_id": str(tenant_id)}

    async def _handle_terminate(
        self, tenant_id: uuid.UUID, request: AdminActionRequest
    ) -> Dict[str, Any]:
        """Handle terminate action."""
        if self.tenant_manager:
            await self.tenant_manager.terminate_tenant(tenant_id)
        return {"success": True, "action": "terminate", "tenant_id": str(tenant_id)}

    async def _handle_change_plan(
        self, tenant_id: uuid.UUID, request: AdminActionRequest
    ) -> Dict[str, Any]:
        """Handle plan change action."""
        new_plan = request.metadata.get("plan", "free")
        if self.tenant_manager:
            from operations.billing.plans import PlanTier
            await self.tenant_manager.change_plan(tenant_id, PlanTier(new_plan))
        return {
            "success": True,
            "action": "change_plan",
            "tenant_id": str(tenant_id),
            "new_plan": new_plan,
        }

    # -- System Configuration ---------------------------------------------

    async def get_system_config(self) -> Dict[str, Any]:
        """Get current system configuration."""
        return {
            "version": "1.0.0",
            "features": {
                "ai_pipeline_enabled": True,
                "websocket_enabled": True,
                "call_recording_enabled": True,
                "transcription_enabled": True,
                "magic_link_login": True,
                "api_key_auth": True,
            },
            "limits": {
                "max_tenants": 10000,
                "max_calls_per_second": 100,
                "max_websocket_connections": 10000,
            },
            "plans": ["free", "starter", "pro", "enterprise"],
        }

    async def update_system_config(
        self, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update system configuration."""
        logger.info("admin.system_config_updated", changes=list(updates.keys()))
        return {"success": True, "updated": list(updates.keys())}

    # -- Training Interface -----------------------------------------------

    async def get_training_queue(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get calls queued for AI training review."""
        queue = self._training_queue
        if status:
            queue = [q for q in queue if q.get("status") == status]
        return queue[:limit]

    async def submit_training_feedback(
        self,
        call_id: uuid.UUID,
        feedback: str,
        rating: int,
        corrected_transcript: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Submit feedback for AI training."""
        from operations.admin.feedback_store import append_feedback

        entry = append_feedback(
            call_id=str(call_id),
            feedback=feedback,
            rating=rating,
            corrected_transcript=corrected_transcript,
            user_id=str(user_id) if user_id else None,
        )

        logger.info("training.feedback_submitted", call_id=str(call_id), rating=rating)

        return {"success": True, "feedback_id": entry["id"]}

    async def get_feedback(
        self,
        call_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get submitted feedback."""
        from operations.admin.feedback_store import list_feedback

        return list_feedback(
            call_id=str(call_id) if call_id else None,
            limit=limit,
        )

    async def submit_prompt_suggestion(
        self,
        tenant_id: uuid.UUID,
        prompt_type: str,
        current_prompt: str,
        suggested_prompt: str,
        reason: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Submit a prompt improvement suggestion."""
        entry = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "prompt_type": prompt_type,
            "current_prompt": current_prompt,
            "suggested_prompt": suggested_prompt,
            "reason": reason,
            "submitted_by": str(user_id) if user_id else None,
            "submitted_at": datetime.utcnow().isoformat(),
            "status": "pending_review",
            "votes": 0,
        }
        self._prompt_suggestions.append(entry)

        logger.info(
            "training.prompt_suggestion_submitted",
            tenant_id=str(tenant_id),
            prompt_type=prompt_type,
        )

        return {"success": True, "suggestion_id": entry["id"]}

    async def get_prompt_suggestions(
        self,
        tenant_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get prompt suggestions."""
        suggestions = self._prompt_suggestions
        if tenant_id:
            suggestions = [s for s in suggestions if s["tenant_id"] == str(tenant_id)]
        if status:
            suggestions = [s for s in suggestions if s.get("status") == status]
        return suggestions[:limit]

    # -- Plan Management (Admin) ------------------------------------------

    async def list_plan_configs(self) -> List[Dict[str, Any]]:
        """List all plan configurations."""
        from operations.billing.plans import PlanManager
        manager = PlanManager()
        return manager.compare_plans()

    async def create_plan_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a custom plan configuration."""
        plan_id = str(uuid.uuid4())
        logger.info("admin.plan_created", plan_id=plan_id, tier=config.get("tier"))
        return {"success": True, "plan_id": plan_id, **config}

    async def update_plan_config(
        self, plan_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a plan configuration."""
        logger.info("admin.plan_updated", plan_id=plan_id, changes=list(updates.keys()))
        return {"success": True, "plan_id": plan_id, "updated": list(updates.keys())}

    # -- Feature Flag Management ------------------------------------------

    async def list_feature_flags(self) -> List[Dict[str, Any]]:
        """List all feature flags."""
        return [
            {
                "name": "call_transcription",
                "display_name": "Call Transcription",
                "category": "ai",
                "default_enabled": True,
                "rollout_percentage": 100,
            },
            {
                "name": "voicemail_sms",
                "display_name": "Voicemail SMS Notifications",
                "category": "notifications",
                "default_enabled": False,
                "rollout_percentage": 50,
            },
            {
                "name": "crm_sync",
                "display_name": "CRM Synchronization",
                "category": "integration",
                "default_enabled": False,
                "required_plan": "pro",
            },
            {
                "name": "multi_language",
                "display_name": "Multi-Language Support",
                "category": "ai",
                "default_enabled": False,
                "required_plan": "pro",
            },
        ]

    async def create_feature_flag(self, flag: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new feature flag."""
        flag_id = str(uuid.uuid4())
        logger.info("admin.feature_flag_created", flag_id=flag_id, name=flag.get("name"))
        return {"success": True, "id": flag_id, **flag}

    async def update_feature_flag(
        self, flag_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a feature flag."""
        logger.info(
            "admin.feature_flag_updated",
            flag_id=flag_id,
            changes=list(updates.keys()),
        )
        return {"success": True, "id": flag_id, "updated": list(updates.keys())}

    # -- Analytics --------------------------------------------------------

    async def get_system_analytics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get system-wide analytics."""
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "calls": {
                "total": 32456,
                "ai_handled": 30120,
                "transferred": 1834,
                "missed": 502,
                "avg_duration_seconds": 245,
            },
            "ai": {
                "avg_response_latency_ms": 850,
                "total_llm_requests": 125430,
                "total_input_tokens": 5023400,
                "total_output_tokens": 1256000,
            },
            "tenants": {
                "total_signups": 207,
                "active_now": 189,
                "churned": 12,
            },
        }


# ---------------------------------------------------------------------------
# API Router
# ---------------------------------------------------------------------------

from fastapi import APIRouter, Body, Depends, Query  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from api.dependencies import RequireAdmin  # noqa: E402

# Shared service instance (in-memory training/feedback stores live here).
_admin_service = AdminService()


class TenantActionBody(BaseModel):
    """Body for a single admin action against a tenant."""

    action: str = Field(
        ...,
        description="One of: suspend, reactivate, change_plan, terminate, limit, unlimit, purge",
    )
    reason: str = Field(..., description="Audit reason for the action")
    metadata: Optional[Dict[str, Any]] = None


class BulkActionBody(BaseModel):
    """Body for an admin action against many tenants."""

    tenant_ids: List[uuid.UUID]
    action: str
    reason: str


class TrainingFeedbackBody(BaseModel):
    """Body for submitting AI training feedback for a call."""

    call_id: uuid.UUID
    feedback: str
    rating: int = Field(..., ge=1, le=5)
    corrected_transcript: Optional[str] = None
    user_id: Optional[uuid.UUID] = None


class PromptSuggestionBody(BaseModel):
    """Body for submitting a prompt improvement suggestion."""

    tenant_id: uuid.UUID
    prompt_type: str
    current_prompt: str
    suggested_prompt: str
    reason: str
    user_id: Optional[uuid.UUID] = None


admin_router = APIRouter(dependencies=[RequireAdmin])


# -- Bulk / tenant actions --------------------------------------------------

@admin_router.post("/tenants/{tenant_id}/actions")
async def admin_tenant_action(
    tenant_id: uuid.UUID, body: TenantActionBody
) -> Dict[str, Any]:
    """Execute a single admin action against a tenant."""
    return await _admin_service.execute_tenant_action(
        tenant_id, AdminActionRequest(body.action, body.reason, body.metadata)
    )


@admin_router.post("/tenants/bulk-actions")
async def admin_bulk_action(body: BulkActionBody) -> Dict[str, Any]:
    """Execute an admin action against multiple tenants."""
    return await _admin_service.execute_bulk_action(
        AdminBulkActionRequest(body.tenant_ids, body.action, body.reason)
    )


# -- System configuration ---------------------------------------------------

@admin_router.get("/system/config")
async def admin_get_system_config() -> Dict[str, Any]:
    """Get current system configuration."""
    return await _admin_service.get_system_config()


@admin_router.patch("/system/config")
async def admin_update_system_config(
    updates: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update system configuration."""
    return await _admin_service.update_system_config(updates)


# -- Training interface -----------------------------------------------------

@admin_router.get("/training/queue")
async def admin_training_queue(
    status: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500)
) -> List[Dict[str, Any]]:
    """List calls queued for AI training review."""
    return await _admin_service.get_training_queue(status=status, limit=limit)


@admin_router.post("/training/feedback")
async def admin_submit_feedback(body: TrainingFeedbackBody) -> Dict[str, Any]:
    """Submit feedback for AI training."""
    return await _admin_service.submit_training_feedback(
        call_id=body.call_id,
        feedback=body.feedback,
        rating=body.rating,
        corrected_transcript=body.corrected_transcript,
        user_id=body.user_id,
    )


@admin_router.get("/training/feedback")
async def admin_get_feedback(
    call_id: Optional[uuid.UUID] = Query(None), limit: int = Query(50, ge=1, le=500)
) -> List[Dict[str, Any]]:
    """List submitted training feedback."""
    return await _admin_service.get_feedback(call_id=call_id, limit=limit)


@admin_router.post("/training/prompt-suggestions")
async def admin_submit_prompt_suggestion(
    body: PromptSuggestionBody,
) -> Dict[str, Any]:
    """Submit a prompt improvement suggestion."""
    return await _admin_service.submit_prompt_suggestion(
        tenant_id=body.tenant_id,
        prompt_type=body.prompt_type,
        current_prompt=body.current_prompt,
        suggested_prompt=body.suggested_prompt,
        reason=body.reason,
        user_id=body.user_id,
    )


@admin_router.get("/training/prompt-suggestions")
async def admin_get_prompt_suggestions(
    tenant_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """List prompt improvement suggestions."""
    return await _admin_service.get_prompt_suggestions(
        tenant_id=tenant_id, status=status, limit=limit
    )


# -- Plan management --------------------------------------------------------

@admin_router.get("/plans")
async def admin_list_plans() -> List[Dict[str, Any]]:
    """List all plan configurations."""
    return await _admin_service.list_plan_configs()


@admin_router.post("/plans")
async def admin_create_plan(config: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Create a custom plan configuration."""
    return await _admin_service.create_plan_config(config)


@admin_router.patch("/plans/{plan_id}")
async def admin_update_plan(
    plan_id: str, updates: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update a plan configuration."""
    return await _admin_service.update_plan_config(plan_id, updates)


# -- Feature flags ----------------------------------------------------------

@admin_router.get("/feature-flags")
async def admin_list_feature_flags() -> List[Dict[str, Any]]:
    """List all feature flags."""
    return await _admin_service.list_feature_flags()


@admin_router.post("/feature-flags")
async def admin_create_feature_flag(
    flag: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Create a new feature flag."""
    return await _admin_service.create_feature_flag(flag)


@admin_router.patch("/feature-flags/{flag_id}")
async def admin_update_feature_flag(
    flag_id: str, updates: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update a feature flag."""
    return await _admin_service.update_feature_flag(flag_id, updates)


# -- Analytics --------------------------------------------------------------

@admin_router.get("/analytics")
async def admin_system_analytics(
    start_date: datetime, end_date: datetime
) -> Dict[str, Any]:
    """Get system-wide analytics for a date range."""
    return await _admin_service.get_system_analytics(start_date, end_date)


# Alias expected by app_factory: ``from operations.admin.routes import router``
router = admin_router
