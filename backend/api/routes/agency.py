"""api/routes/agency.py - Agency admin routes for multi-tenant management.

Endpoints (mounted at /api/v1/agency by api/main.py):
    GET  /overview          -> aggregate stats across all tenants
    GET  /clients           -> list all client tenants with summary metrics
    GET  /clients/{id}      -> detailed client view (calls, performance, config)
    POST /clients           -> provision a new client tenant
    PUT  /clients/{id}      -> update client configuration
    GET  /clients/{id}/calls -> client's calls with filters
    GET  /clients/{id}/transcripts -> client's transcripts
    GET  /clients/{id}/performance -> client's performance metrics
    POST /clients/{id}/onboarding/advance -> advance onboarding checklist
    GET  /onboarding/pipeline -> all clients' onboarding status
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from api.dependencies import CurrentUser, get_db_session
from backend.db.models.tenant import Tenant
from backend.db.models.call import Call
from backend.db.models.user import User
from backend.db.models.enums import UserRole
from backend.integrations.retell.service import (
    create_agent,
    import_twilio_number,
    is_configured as retell_configured,
)
from backend.integrations.twilio.service import (
    assign_number_to_trunk,
    buy_number,
    get_termination_uri,
    is_configured as twilio_configured,
    list_available_numbers,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/agency", tags=["Agency Admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ClientSummary(BaseModel):
    """Summary view of a client tenant for the agency dashboard."""
    id: str
    slug: str
    name: str
    plan: str
    status: str
    industry: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[str] = None
    calls_this_month: int = 0
    calls_last_month: int = 0
    revenue_mtd: float = 0.0
    onboarding_step: int = 0
    onboarding_complete: bool = False


class AgencyOverview(BaseModel):
    """Aggregate stats across all managed tenants."""
    total_clients: int = 0
    active_clients: int = 0
    trial_clients: int = 0
    total_calls_this_month: int = 0
    total_calls_last_month: int = 0
    mrr: float = 0.0
    arr: float = 0.0
    avg_calls_per_client: float = 0.0
    top_industries: list[dict[str, Any]] = []
    onboarding_pipeline: dict[str, int] = {}


class OnboardingStep(BaseModel):
    """A single step in the onboarding checklist."""
    step: int
    name: str
    description: str
    completed: bool
    completed_at: Optional[str] = None


class ClientDetail(BaseModel):
    """Full client detail for agency view."""
    id: str
    slug: str
    name: str
    plan: str
    status: str
    industry: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    created_at: Optional[str] = None
    greeting: Optional[str] = None
    onboarding: list[OnboardingStep] = []
    calls_this_month: int = 0
    avg_answer_time: Optional[float] = None
    booking_rate: Optional[float] = None
    revenue_mtd: float = 0.0


class CreateClientRequest(BaseModel):
    """Request to provision a new client tenant."""
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=3, max_length=63)
    phone: str = Field(..., description="Business phone in E.164 format")
    email: str
    industry: str = Field(default="other")
    plan: str = Field(default="starter")
    timezone: str = Field(default="America/New_York")
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Onboarding checklist definition
# ---------------------------------------------------------------------------

ONBOARDING_STEPS = [
    {"step": 1, "name": "Intake form", "description": "Client submits business info, hours, services, FAQs"},
    {"step": 2, "name": "AI configured", "description": "System prompt, greeting, and knowledge base set up"},
    {"step": 3, "name": "Phone provisioned", "description": "Number assigned or forwarding configured"},
    {"step": 4, "name": "Calendar connected", "description": "Google Calendar / CRM integration linked"},
    {"step": 5, "name": "Test calls", "description": "Internal test calls completed and verified"},
    {"step": 6, "name": "Client review", "description": "Client confirms greeting and behavior"},
    {"step": 7, "name": "Go live", "description": "Calls routed to Owlbell, monitoring active"},
    {"step": 8, "name": "First week review", "description": "7-day performance review with account manager"},
]

PLAN_PRICES = {"starter": 297, "professional": 797, "pro_plus": 1497, "enterprise": 2000}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tenant(db: Any, tenant_id: str) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Client '{tenant_id}' not found")
    return tenant


def _cfg(tenant: Tenant) -> dict[str, Any]:
    """Return the tenant's config_json dict, initialising if missing."""
    if tenant.config_json is None:
        tenant.config_json = {}
    return tenant.config_json


def _get_config_val(tenant: Tenant, key: str, default: Any = "") -> Any:
    return _cfg(tenant).get(key, default)


async def _set_config_val(db: Any, tenant: Tenant, key: str, value: Any) -> None:
    cfg = _cfg(tenant)
    cfg[key] = value
    tenant.config_json = cfg
    await db.commit()
    await db.refresh(tenant)


async def _count_calls_for_tenant(db: Any, tenant_id: str, since: Optional[datetime] = None) -> int:
    stmt = select(func.count(Call.id)).where(Call.tenant_id == tenant_id)
    if since:
        stmt = stmt.where(Call.created_at >= since)
    result = await db.execute(stmt)
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/overview")
async def get_overview(user=CurrentUser) -> dict[str, Any]:
    """Aggregate stats across all managed tenants."""
    async for db in get_db_session():
        break

    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    clients = result.scalars().all()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    active = [c for c in clients if c.status == "active"]
    trial = [c for c in clients if c.status == "trial"]

    mrr = sum(PLAN_PRICES.get(c.plan_tier or "", 0) for c in active)

    industries: dict[str, int] = {}
    for c in clients:
        ind = c.industry or "other"
        industries[ind] = industries.get(ind, 0) + 1
    top_industries = sorted(
        [{"industry": k, "count": v} for k, v in industries.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    pipeline: dict[str, int] = {}
    for c in clients:
        cfg = _cfg(c)
        step = int(cfg.get("onboarding_step", 0))
        complete = bool(cfg.get("onboarding_complete", False))
        label = "Complete" if complete else f"Step {step}"
        pipeline[label] = pipeline.get(label, 0) + 1

    overview = AgencyOverview(
        total_clients=len(clients),
        active_clients=len(active),
        trial_clients=len(trial),
        total_calls_this_month=sum(int(_cfg(c).get("calls_this_month", 0)) for c in clients),
        total_calls_last_month=sum(int(_cfg(c).get("calls_last_month", 0)) for c in clients),
        mrr=mrr,
        arr=mrr * 12,
        avg_calls_per_client=round(
            sum(int(_cfg(c).get("calls_this_month", 0)) for c in clients) / max(len(clients), 1), 1
        ),
        top_industries=top_industries,
        onboarding_pipeline=pipeline,
    )
    return {"success": True, "data": overview.model_dump()}


@router.get("/clients")
async def list_clients(
    status_filter: Optional[str] = Query(None, alias="status"),
    industry: Optional[str] = None,
    search: Optional[str] = None,
    user=CurrentUser,
) -> dict[str, Any]:
    """List all client tenants with summary metrics."""
    async for db in get_db_session():
        break

    stmt = select(Tenant).order_by(Tenant.created_at.desc())

    if status_filter:
        stmt = stmt.where(Tenant.status == status_filter)
    if industry:
        stmt = stmt.where(Tenant.industry == industry)
    if search:
        q = f"%{search}%"
        stmt = stmt.where(Tenant.name.ilike(q) | Tenant.slug.ilike(q))

    result = await db.execute(stmt)
    clients = result.scalars().all()

    summaries = []
    for c in clients:
        cfg = _cfg(c)
        summaries.append(ClientSummary(
            id=str(c.id),
            slug=c.slug or "",
            name=c.name or "",
            plan=c.plan_tier or "starter",
            status=c.status or "active",
            industry=c.industry,
            phone=c.business_phone,
            created_at=c.created_at.isoformat() if c.created_at else None,
            calls_this_month=int(cfg.get("calls_this_month", 0)),
            calls_last_month=int(cfg.get("calls_last_month", 0)),
            revenue_mtd=float(cfg.get("revenue_mtd", 0)),
            onboarding_step=int(cfg.get("onboarding_step", 0)),
            onboarding_complete=bool(cfg.get("onboarding_complete", False)),
        ))

    return {"success": True, "data": [s.model_dump() for s in summaries]}


@router.get("/clients/{client_id}")
async def get_client_detail(client_id: str, user=CurrentUser) -> dict[str, Any]:
    """Detailed client view with onboarding status and performance."""
    async for db in get_db_session():
        break
    tenant = await _get_tenant(db, client_id)
    cfg = _cfg(tenant)

    current_step = int(cfg.get("onboarding_step", 0))
    onboarding = []
    for step_def in ONBOARDING_STEPS:
        onboarding.append(OnboardingStep(
            step=step_def["step"],
            name=step_def["name"],
            description=step_def["description"],
            completed=step_def["step"] <= current_step,
        ))

    detail = ClientDetail(
        id=str(tenant.id),
        slug=tenant.slug or "",
        name=tenant.name or "",
        plan=tenant.plan_tier or "starter",
        status=tenant.status or "active",
        industry=tenant.industry,
        phone=tenant.business_phone,
        email=tenant.business_email,
        timezone=tenant.timezone if hasattr(tenant, "timezone") else None,
        created_at=tenant.created_at.isoformat() if tenant.created_at else None,
        greeting=cfg.get("greeting"),
        onboarding=onboarding,
        calls_this_month=int(cfg.get("calls_this_month", 0)),
        avg_answer_time=float(cfg["avg_answer_time"]) if cfg.get("avg_answer_time") else None,
        booking_rate=float(cfg["booking_rate"]) if cfg.get("booking_rate") else None,
        revenue_mtd=float(cfg.get("revenue_mtd", 0)),
    )
    return {"success": True, "data": detail.model_dump()}


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def create_client(body: CreateClientRequest, user=CurrentUser) -> dict[str, Any]:
    """Provision a new client tenant via the agency."""
    async for db in get_db_session():
        break

    slug_check = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if slug_check.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Slug '{body.slug}' is already taken")

    owner_email = body.owner_email or body.email
    owner_name = body.owner_name or body.name

    tenant = Tenant(
        slug=body.slug,
        name=body.name,
        plan_tier=body.plan,
        status="trial",
        industry=body.industry,
        business_phone=body.phone,
        business_email=body.email,
        config_json={
            "calls_this_month": 0,
            "calls_last_month": 0,
            "revenue_mtd": 0.0,
            "onboarding_step": 0,
            "onboarding_complete": False,
            "owner_email": owner_email,
            "owner_name": owner_name,
        },
    )
    db.add(tenant)
    await db.flush()

    user = User(
        email=owner_email,
        password_hash="",
        first_name=owner_name.split()[0],
        last_name=" ".join(owner_name.split()[1:]) if len(owner_name.split()) > 1 else "",
        role=UserRole.ADMIN,
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(tenant)

    # ── Provision Twilio number + Retell AI agent ─────────────────────
    # Best-effort: client creation must not fail if telephony setup does.
    retell_agent_id = None
    assigned_phone = None

    if twilio_configured():
        try:
            available = await list_available_numbers(limit=5)
            if available:
                number_to_buy = available[0]["phone_number"]
                buy_result = await buy_number(
                    phone_number=number_to_buy,
                    friendly_name=f"Owlbell - {body.name}",
                )
                if buy_result.get("success"):
                    assigned_phone = number_to_buy
                    twilio_sid = buy_result.get("sid")

                    # Assign the number to the Elastic SIP Trunk
                    if twilio_sid:
                        trunk_result = await assign_number_to_trunk(twilio_sid)
                        if not trunk_result.get("success"):
                            logger.warning("agency.trunk_assign_failed", client_id=str(tenant.id), error=trunk_result.get("error"))

                    cfg = _cfg(tenant)
                    cfg["assigned_phone"] = assigned_phone
                    if twilio_sid:
                        cfg["twilio_phone_sid"] = twilio_sid
                    tenant.config_json = cfg
                    await db.commit()

                    logger.info(
                        "agency.twilio_number_provisioned",
                        client_id=str(tenant.id),
                        phone=assigned_phone,
                    )
        except Exception as exc:
            logger.warning("agency.twilio_provision_failed", client_id=str(tenant.id), error=str(exc))

    if retell_configured():
        try:
            from backend.db.prompt_templates import get_prompt_templates

            templates = get_prompt_templates(body.industry, body.name)
            system_prompt = templates["system"]
            greeting = templates["greeting"]

            agent_result = create_agent(
                tenant_id=str(tenant.id),
                name=f"{body.name} Receptionist",
                greeting=greeting,
                system_prompt=system_prompt,
            )
            if agent_result.get("success"):
                retell_agent_id = agent_result["agent_id"]
                cfg = _cfg(tenant)
                cfg["retell_agent_id"] = retell_agent_id
                tenant.config_json = cfg
                await db.commit()

                logger.info(
                    "agency.retell_agent_created",
                    client_id=str(tenant.id),
                    agent_id=retell_agent_id,
                )

                termination_uri = get_termination_uri()
                if termination_uri and assigned_phone:
                    import_result = import_twilio_number(
                        phone_number=assigned_phone,
                        termination_uri=termination_uri,
                        agent_id=retell_agent_id,
                        nickname=f"{body.name} Receptionist",
                    )
                    if import_result.get("success"):
                        logger.info("agency.number_imported_to_retell", client_id=str(tenant.id))
                    else:
                        logger.warning("agency.retell_import_failed", client_id=str(tenant.id), error=import_result.get("error"))
        except Exception as exc:
            logger.warning("agency.retell_provision_failed", client_id=str(tenant.id), error=str(exc))

    # Spin up the DB-backed onboarding pipeline + email sequence
    try:
        from backend.dependencies import get_session_maker
        from operations.onboarding import automation, email_sequence

        session_maker = get_session_maker()
        if session_maker is not None:
            pipeline = await automation.create_pipeline(
                session_maker,
                tenant_id=str(tenant.id),
                tenant_name=body.name,
                tenant_email=body.email,
            )
            await email_sequence.create_sequence(
                session_maker,
                tenant_id=str(tenant.id),
                contact_name=body.owner_name or body.name,
                business_name=body.name,
                contact_email=body.owner_email or body.email,
                pipeline_id=pipeline.id,
            )
    except Exception as exc:
        logger.warning("agency.onboarding_setup_failed", client_id=str(tenant.id), error=str(exc))

    logger.info("agency.client_created", client_id=str(tenant.id), name=body.name, plan=body.plan)
    return {"success": True, "data": {"id": str(tenant.id), "slug": tenant.slug}}


@router.put("/clients/{client_id}")
async def update_client(
    client_id: str,
    name: Optional[str] = None,
    plan: Optional[str] = None,
    status_val: Optional[str] = Query(None, alias="status"),
    greeting: Optional[str] = None,
    user=CurrentUser,
) -> dict[str, Any]:
    """Update client configuration."""
    async for db in get_db_session():
        break

    tenant = await _get_tenant(db, client_id)

    if name is not None:
        tenant.name = name
    if plan is not None:
        tenant.plan_tier = plan
    if status_val is not None:
        tenant.status = status_val
    if greeting is not None:
        cfg = _cfg(tenant)
        cfg["greeting"] = greeting
        tenant.config_json = cfg

    await db.commit()
    await db.refresh(tenant)
    return {"success": True, "data": {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name}}


@router.get("/clients/{client_id}/calls")
async def get_client_calls(
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=CurrentUser,
) -> dict[str, Any]:
    """Get a client's calls with pagination."""
    async for db in get_db_session():
        break
    await _get_tenant(db, client_id)

    count_result = await db.execute(
        select(func.count(Call.id)).where(Call.tenant_id == client_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Call)
        .where(Call.tenant_id == client_id)
        .order_by(Call.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    calls = result.scalars().all()

    return {
        "success": True,
        "data": {
            "client_id": client_id,
            "calls": [
                {
                    "id": str(call.id),
                    "caller": getattr(call, "caller_number", None),
                    "started_at": call.created_at.isoformat() if call.created_at else None,
                    "duration": getattr(call, "duration_seconds", None),
                    "status": getattr(call, "status", None),
                }
                for call in calls
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/clients/{client_id}/transcripts")
async def get_client_transcripts(
    client_id: str,
    limit: int = Query(20, ge=1, le=100),
    user=CurrentUser,
) -> dict[str, Any]:
    """Get a client's recent transcripts."""
    async for db in get_db_session():
        break
    await _get_tenant(db, client_id)

    count_result = await db.execute(
        select(func.count(Call.id)).where(Call.tenant_id == client_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Call)
        .where(Call.tenant_id == client_id)
        .order_by(Call.created_at.desc())
        .limit(limit)
    )
    calls = result.scalars().all()

    return {
        "success": True,
        "data": {
            "client_id": client_id,
            "transcripts": [
                {
                    "id": str(call.id),
                    "started_at": call.created_at.isoformat() if call.created_at else None,
                    "transcript": getattr(call, "transcript", None),
                }
                for call in calls
            ],
            "total": total,
        },
    }


@router.get("/clients/{client_id}/performance")
async def get_client_performance(
    client_id: str,
    days: int = Query(30, ge=1, le=365),
    user=CurrentUser,
) -> dict[str, Any]:
    """Get a client's performance metrics over a time range."""
    async for db in get_db_session():
        break
    tenant = await _get_tenant(db, client_id)
    cfg = _cfg(tenant)

    since = datetime.now(timezone.utc) - timedelta(days=days)

    call_count = await _count_calls_for_tenant(db, client_id, since=since)

    avg_result = await db.execute(
        select(func.avg(Call.duration_seconds)).where(
            Call.tenant_id == client_id,
            Call.created_at >= since,
        )
    )
    avg_duration = avg_result.scalar()

    return {
        "success": True,
        "data": {
            "client_id": client_id,
            "period_days": days,
            "total_calls": call_count,
            "avg_answer_time": float(avg_duration) if avg_duration else None,
            "booking_rate": float(cfg["booking_rate"]) if cfg.get("booking_rate") else None,
            "missed_call_rate": None,
            "calls_by_hour": {},
            "calls_by_day": {},
            "top_intents": [],
        },
    }


@router.post("/clients/{client_id}/onboarding/advance")
async def advance_onboarding(client_id: str, user=CurrentUser) -> dict[str, Any]:
    """Advance the onboarding checklist to the next step."""
    async for db in get_db_session():
        break
    tenant = await _get_tenant(db, client_id)
    cfg = _cfg(tenant)

    current = int(cfg.get("onboarding_step", 0))
    if current >= len(ONBOARDING_STEPS):
        return {"success": True, "data": {"message": "Onboarding already complete", "step": current}}

    new_step = current + 1
    complete = new_step >= len(ONBOARDING_STEPS)

    cfg["onboarding_step"] = new_step
    cfg["onboarding_complete"] = complete
    tenant.config_json = cfg
    if complete:
        tenant.status = "active"
    await db.commit()

    logger.info("agency.onboarding_advanced", client_id=client_id, step=new_step)
    return {
        "success": True,
        "data": {
            "client_id": client_id,
            "step": new_step,
            "complete": complete,
            "next_step": ONBOARDING_STEPS[new_step] if new_step < len(ONBOARDING_STEPS) else None,
        },
    }


@router.get("/onboarding/pipeline")
async def get_onboarding_pipeline(user=CurrentUser) -> dict[str, Any]:
    """Overview of all clients' onboarding status."""
    async for db in get_db_session():
        break

    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    clients = result.scalars().all()

    pipeline = []
    for tenant in clients:
        cfg = _cfg(tenant)
        step = int(cfg.get("onboarding_step", 0))
        complete = bool(cfg.get("onboarding_complete", False))
        pipeline.append({
            "client_id": str(tenant.id),
            "name": tenant.name or "",
            "slug": tenant.slug or "",
            "current_step": step,
            "total_steps": len(ONBOARDING_STEPS),
            "complete": complete,
            "current_step_name": ONBOARDING_STEPS[step - 1]["name"] if 0 < step <= len(ONBOARDING_STEPS) else "Not started",
        })

    return {
        "success": True,
        "data": {
            "steps": ONBOARDING_STEPS,
            "clients": sorted(pipeline, key=lambda x: x["current_step"], reverse=True),
        },
    }
