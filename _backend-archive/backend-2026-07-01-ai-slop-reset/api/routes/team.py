"""api/routes/team.py - Team management route handlers (8 endpoints).

Provides team member CRUD, invites, and notification preferences.
Uses the User model for team members and notification_prefs JSONB.
Invitations are persisted per-tenant in TenantConfig.integrations["team_invites"].
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from passlib.context import CryptContext

from api.dependencies import CurrentTenant, CurrentUser, DBSession, get_db_session
from api.schemas.base import ResponseMeta, SuccessResponse, UserRole
from api.schemas.team import (
    NotificationPreferences,
    TeamListResponse,
    TeamMember,
    TeamMemberCreateRequest,
    TeamMemberInviteAccept,
    TeamMemberUpdateRequest,
)
from backend.db.models.enums import UserRole as DBUserRole
from backend.db.models.tenant import TenantConfig
from backend.db.models.user import User
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/team", tags=["Team Management"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_INVITES_KEY = "team_invites"

# ---------------------------------------------------------------------------
# Invitation persistence (TenantConfig.integrations JSONB)
# ---------------------------------------------------------------------------


async def _get_or_create_tenant_config(db: AsyncSession, tenant_id: uuid.UUID) -> TenantConfig:
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == tenant_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = TenantConfig(tenant_id=tenant_id)
        db.add(cfg)
        await db.flush()
    return cfg


async def _get_invites(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    cfg = await _get_or_create_tenant_config(db, tenant_id)
    integrations = dict(cfg.integrations or {})
    return dict(integrations.get(_INVITES_KEY, {}))


async def _save_invite(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    invite_dict: dict[str, Any],
    token: str | None = None,
) -> str:
    cfg = await _get_or_create_tenant_config(db, tenant_id)
    integrations = dict(cfg.integrations or {})
    invites = dict(integrations.get(_INVITES_KEY, {}))
    invite_token = token or secrets.token_urlsafe(32)
    invites[invite_token] = invite_dict
    integrations[_INVITES_KEY] = invites
    cfg.integrations = integrations
    await db.flush()
    return invite_token


async def _pop_invite_by_token(
    db: AsyncSession,
    token: str,
) -> tuple[dict[str, Any], uuid.UUID] | None:
    result = await db.execute(select(TenantConfig))
    for cfg in result.scalars().all():
        integrations = dict(cfg.integrations or {})
        invites = dict(integrations.get(_INVITES_KEY, {}))
        if token not in invites:
            continue
        invite = invites.pop(token)
        integrations[_INVITES_KEY] = invites
        cfg.integrations = integrations
        await db.flush()
        return invite, cfg.tenant_id
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_to_team_member(user: User) -> TeamMember:
    """Convert a User ORM row to the TeamMember schema."""
    prefs = user.notification_prefs or {}
    department = prefs.get("department")
    return TeamMember(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=UserRole(user.role.value) if user.role else UserRole.VIEWER,
        phone=user.phone,
        department=department,
        is_active=user.is_active,
        notification_preferences=prefs,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


_DEFAULT_NOTIFICATION_PREFS: dict[str, Any] = {
    "email_new_calls": True,
    "email_new_messages": True,
    "email_new_appointments": True,
    "email_daily_digest": False,
    "sms_urgent_only": True,
    "slack_notifications": False,
}

_DEFAULT_USER_NOTIFICATION_PREFS: dict[str, Any] = {
    "email_call_summary": True,
    "email_voicemail": True,
    "email_appointment": True,
    "sms_call_summary": False,
    "dashboard_sound": True,
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/members",
    response_model=SuccessResponse[TeamListResponse],
    summary="List team members",
    description="List all team members for the tenant.",
)
async def list_members(
    page: int = 1,
    per_page: int = 20,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[TeamListResponse]:
    """List team members for the tenant."""
    repo = TenantScopedRepository(db, User, tenant.id)

    all_members = await repo.get_all(limit=per_page, offset=(page - 1) * per_page)
    total = await repo.count()

    by_role: dict[str, int] = {}
    for u in all_members:
        role = u.role.value if u.role else "viewer"
        by_role[role] = by_role.get(role, 0) + 1

    return SuccessResponse(
        data=TeamListResponse(
            items=[_user_to_team_member(u) for u in all_members],
            total=total,
            by_role=by_role,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/members",
    response_model=SuccessResponse[TeamMember],
    status_code=status.HTTP_201_CREATED,
    summary="Invite member",
    description="Invite a new team member.",
)
async def invite_member(
    body: TeamMemberCreateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[TeamMember]:
    """Invite a team member by creating a User record."""
    prefs = {**_DEFAULT_NOTIFICATION_PREFS}
    if body.department:
        prefs["department"] = body.department

    user_prefs = {**_DEFAULT_USER_NOTIFICATION_PREFS}

    new_user = User(
        tenant_id=tenant.id,
        email=str(body.email),
        first_name=body.first_name or "",
        last_name=body.last_name or "",
        role=DBUserRole(body.role.value) if body.role else DBUserRole.VIEWER,
        phone=body.phone,
        is_active=False,
        notification_prefs=user_prefs,
        password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    if body.send_invite:
        await _save_invite(
            db,
            tenant.id,
            {
                "email": str(body.email),
                "user_id": str(new_user.id),
                "tenant_id": str(tenant.id),
                "invited_by": str(user.id),
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            },
        )
        logger.info("team.invite_sent", email=str(body.email), user_id=str(new_user.id))

    logger.info("team.member_created", member_id=str(new_user.id))

    return SuccessResponse(
        data=_user_to_team_member(new_user),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/members/{member_id}",
    response_model=SuccessResponse[TeamMember],
    summary="Get member",
    description="Get a team member by ID.",
)
async def get_member(
    member_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[TeamMember]:
    """Get a team member by ID."""
    repo = TenantScopedRepository(db, User, tenant.id)
    user = await repo.get_by_id(member_id)
    if not user:
        raise HTTPException(status_code=404, detail="Team member not found")

    return SuccessResponse(
        data=_user_to_team_member(user),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/members/{member_id}",
    response_model=SuccessResponse[TeamMember],
    summary="Update member",
    description="Update a team member's details.",
)
async def update_member(
    member_id: uuid.UUID,
    body: TeamMemberUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[TeamMember]:
    """Update a team member's details."""
    repo = TenantScopedRepository(db, User, tenant.id)
    db_user = await repo.get_by_id(member_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Team member not found")

    update_data: dict[str, Any] = {}
    if body.first_name is not None:
        update_data["first_name"] = body.first_name
    if body.last_name is not None:
        update_data["last_name"] = body.last_name
    if body.role is not None:
        update_data["role"] = DBUserRole(body.role.value)
    if body.phone is not None:
        update_data["phone"] = body.phone
    if body.is_active is not None:
        update_data["is_active"] = body.is_active
    if body.department is not None or body.notification_preferences is not None:
        prefs = dict(db_user.notification_prefs or _DEFAULT_USER_NOTIFICATION_PREFS)
        if body.department is not None:
            if body.department:
                prefs["department"] = body.department
            else:
                prefs.pop("department", None)
        if body.notification_preferences is not None:
            prefs.update({
                "email_call_summary": body.notification_preferences.get("email_new_calls", prefs.get("email_call_summary", True)),
                "email_voicemail": body.notification_preferences.get("email_new_messages", prefs.get("email_voicemail", True)),
                "email_appointment": body.notification_preferences.get("email_new_appointments", prefs.get("email_appointment", True)),
            })
        update_data["notification_prefs"] = prefs

    if update_data:
        db_user = await repo.update(member_id, **update_data)
        await db.refresh(db_user)

    logger.info("team.member_updated", member_id=str(member_id))

    return SuccessResponse(
        data=_user_to_team_member(db_user),
        meta=ResponseMeta(request_id=""),
    )


@router.delete(
    "/members/{member_id}",
    response_model=SuccessResponse[dict],
    summary="Remove member",
    description="Remove a team member from the tenant.",
)
async def remove_member(
    member_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Remove a team member (soft-delete via is_active=False)."""
    repo = TenantScopedRepository(db, User, tenant.id)
    db_user = await repo.get_by_id(member_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Team member not found")

    db_user.is_active = False
    await db.flush()

    logger.info("team.member_removed", member_id=str(member_id))

    return SuccessResponse(
        data={"message": "Team member removed successfully"},
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/invites",
    response_model=SuccessResponse[dict],
    summary="Send invite",
    description="Send or resend an invitation to a team member.",
)
async def send_invite(
    request: Request,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Send or resend an invitation."""
    body_data = await request.json() if await request.body() else {}
    email = body_data.get("email", "")
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()

    invite_token = await _save_invite(
        db,
        tenant.id,
        {
            "email": email,
            "tenant_id": str(tenant.id),
            "invited_by": str(user.id),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
        },
    )

    logger.info("team.invite_resent", email=email)

    return SuccessResponse(
        data={
            "message": f"Invitation sent to {email}",
            "token": invite_token,
            "expires_at": expires_at,
        },
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/invite/accept",
    response_model=SuccessResponse[dict],
    summary="Accept invite",
    description="Accept a team invitation with token and set password.",
)
async def accept_invite(
    body: TeamMemberInviteAccept,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Accept team invite by updating the user's password."""
    popped = await _pop_invite_by_token(db, body.token)
    if not popped:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")
    invite, _tenant_id = popped

    user_id = invite.get("user_id")
    if user_id:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.password_hash = pwd_context.hash(body.password)
            db_user.is_active = True
            await db.flush()

    logger.info("team.invite_accepted", email=invite.get("email"))

    return SuccessResponse(
        data={"message": "Invitation accepted successfully. You can now log in."},
        meta=ResponseMeta(request_id=""),
    )


# ---------------------------------------------------------------------------
# Notification Preferences
# ---------------------------------------------------------------------------


@router.get(
    "/notifications/preferences",
    response_model=SuccessResponse[NotificationPreferences],
    summary="Get preferences",
    description="Get current user's notification preferences.",
)
async def get_notification_preferences(
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[NotificationPreferences]:
    """Get notification preferences for the current user."""
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one_or_none()

    if db_user and db_user.notification_prefs:
        prefs = db_user.notification_prefs
    else:
        prefs = _DEFAULT_USER_NOTIFICATION_PREFS

    mapped = NotificationPreferences(
        email_new_calls=prefs.get("email_call_summary", prefs.get("email_new_calls", True)),
        email_new_messages=prefs.get("email_voicemail", prefs.get("email_new_messages", True)),
        email_new_appointments=prefs.get("email_appointment", prefs.get("email_new_appointments", True)),
        email_daily_digest=prefs.get("email_daily_digest", False),
        sms_urgent_only=prefs.get("sms_urgent_only", True),
        slack_notifications=prefs.get("slack_notifications", False),
        quiet_hours_start=prefs.get("quiet_hours_start"),
        quiet_hours_end=prefs.get("quiet_hours_end"),
    )

    return SuccessResponse(
        data=mapped,
        meta=ResponseMeta(request_id=""),
    )


@router.put(
    "/notifications/preferences",
    response_model=SuccessResponse[NotificationPreferences],
    summary="Update preferences",
    description="Update notification preferences.",
)
async def update_notification_preferences(
    body: NotificationPreferences,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[NotificationPreferences]:
    """Update notification preferences for the current user."""
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one_or_none()

    prefs = dict(db_user.notification_prefs or _DEFAULT_USER_NOTIFICATION_PREFS) if db_user else dict(_DEFAULT_USER_NOTIFICATION_PREFS)

    prefs["email_call_summary"] = body.email_new_calls
    prefs["email_voicemail"] = body.email_new_messages
    prefs["email_appointment"] = body.email_new_appointments
    prefs["email_daily_digest"] = body.email_daily_digest
    prefs["sms_urgent_only"] = body.sms_urgent_only
    prefs["slack_notifications"] = body.slack_notifications
    if body.quiet_hours_start:
        prefs["quiet_hours_start"] = body.quiet_hours_start
    else:
        prefs.pop("quiet_hours_start", None)
    if body.quiet_hours_end:
        prefs["quiet_hours_end"] = body.quiet_hours_end
    else:
        prefs.pop("quiet_hours_end", None)

    if db_user:
        db_user.notification_prefs = prefs
        await db.flush()

    return SuccessResponse(
        data=body,
        meta=ResponseMeta(request_id=""),
    )
