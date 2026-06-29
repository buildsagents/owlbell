"""api/routes/business.py - Business settings route handlers (14 endpoints).

Provides business profile, AI configuration, FAQ management,
business hours, and routing rules.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, CurrentUser, DBSession
from api.schemas.base import ResponseMeta, SuccessResponse
from api.schemas.business import (
    AICallHandlingConfig,
    AIVoiceConfig,
    AIHandlingUpdateRequest,
    AIVoiceUpdateRequest,
    BusinessAddress,
    BusinessProfile,
    BusinessSettings,
    FAQBulkImportRequest,
    FAQCreateRequest,
    FAQEntry,
    FAQListResponse,
    FAQUpdateRequest,
    ProfileUpdateRequest,
    RoutingRule,
    RoutingRuleUpdateRequest,
)
from backend.db.models.business import FAQEntry as FAQEntryModel
from backend.db.models.tenant import Tenant, TenantConfig
from backend.domain.scripts.version_service import append_script_version, list_script_versions
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/business", tags=["Business Settings"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_tenant_model(db: Any, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def _get_or_create_tenant_config(db: Any, tenant_id: uuid.UUID) -> TenantConfig:
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = TenantConfig(tenant_id=tenant_id)
        db.add(config)
        await db.flush()
    return config


def _faq_db_to_schema(faq: FAQEntryModel) -> FAQEntry:
    return FAQEntry(
        id=faq.id,
        tenant_id=faq.tenant_id,
        question=faq.question,
        answer=faq.answer,
        category=faq.category,
        tags=faq.tags_json or [],
        is_active=faq.is_active,
        hit_count=faq.use_count,
        created_at=faq.created_at,
        updated_at=faq.updated_at,
    )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get(
    "/profile",
    response_model=SuccessResponse[BusinessProfile],
    summary="Get business profile",
    description="Get the business profile information.",
)
async def get_profile(
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[BusinessProfile]:
    """Get business profile."""
    t = await _get_tenant_model(db, tenant.id)

    address = None
    if t.business_address:
        try:
            addr_data = json.loads(t.business_address)
            address = BusinessAddress(**addr_data)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    config_json = t.config_json or {}

    profile = BusinessProfile(
        id=t.id,
        name=t.name,
        slug=t.slug,
        description=config_json.get("description"),
        phone_number=t.business_phone or "",
        email=t.business_email,
        website=t.business_website,
        address=address,
        timezone=t.business_timezone,
        industry=t.industry,
        logo_url=config_json.get("logo_url"),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )
    return SuccessResponse(data=profile, meta=ResponseMeta(request_id=""))


@router.patch(
    "/profile",
    response_model=SuccessResponse[BusinessProfile],
    summary="Update business profile",
    description="Update the business profile.",
)
async def update_profile(
    body: ProfileUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[BusinessProfile]:
    """Update business profile."""
    t = await _get_tenant_model(db, tenant.id)

    if body.name is not None:
        t.name = body.name
    if body.phone_number is not None:
        t.business_phone = body.phone_number
    if body.email is not None:
        t.business_email = body.email
    if body.website is not None:
        t.business_website = body.website
    if body.address is not None:
        t.business_address = json.dumps(body.address.model_dump(exclude_none=True))
    if body.timezone is not None:
        t.business_timezone = body.timezone
    if body.industry is not None:
        t.industry = body.industry
    if body.description is not None:
        t.config_json = {**(t.config_json or {}), "description": body.description}

    await db.flush()
    return await get_profile(tenant=tenant, db=db)


# ---------------------------------------------------------------------------
# Settings (combined)
# ---------------------------------------------------------------------------


@router.get(
    "/settings",
    response_model=SuccessResponse[BusinessSettings],
    summary="Get business settings",
    description="Get complete business settings including AI config.",
)
async def get_settings(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[BusinessSettings]:
    """Get complete business settings."""
    profile_resp = await get_profile(tenant=tenant, db=db)
    voice_resp = await get_voice_config(tenant=tenant, db=db)
    handling_resp = await get_handling_config(tenant=tenant, db=db)

    return SuccessResponse(
        data=BusinessSettings(
            profile=profile_resp.data,
            ai_voice=voice_resp.data,
            ai_handling=handling_resp.data,
        ),
        meta=ResponseMeta(request_id=""),
    )


# ---------------------------------------------------------------------------
# AI Voice Config
# ---------------------------------------------------------------------------


@router.get(
    "/ai/voice",
    response_model=SuccessResponse[AIVoiceConfig],
    summary="Get voice config",
    description="Get AI voice configuration.",
)
async def get_voice_config(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AIVoiceConfig]:
    """Get AI voice config."""
    config = await _get_or_create_tenant_config(db, tenant.id)
    ai = config.ai_settings or {}
    voice = ai.get("voice", {})

    return SuccessResponse(
        data=AIVoiceConfig(
            voice_id=voice.get("voice_id", "en_US-lessac-medium"),
            greeting_template=voice.get(
                "greeting_template",
                "Hello, thank you for calling {business_name}. This is your AI assistant. How may I help you today?",
            ),
            personality=voice.get("personality", "professional_friendly"),
            speaking_rate=voice.get("speaking_rate", 1.0),
            language=voice.get("language", "en"),
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/ai/voice",
    response_model=SuccessResponse[AIVoiceConfig],
    summary="Update voice config",
    description="Update AI voice configuration.",
)
async def update_voice_config(
    body: AIVoiceUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AIVoiceConfig]:
    """Update AI voice configuration."""
    config = await _get_or_create_tenant_config(db, tenant.id)
    ai = dict(config.ai_settings or {})
    voice = dict(ai.get("voice", {}))

    update = body.model_dump(exclude_none=True)
    voice.update(update)
    ai["voice"] = voice
    config.ai_settings = ai

    await db.flush()
    logger.info("ai_voice.updated", tenant_id=str(tenant.id))
    return await get_voice_config(tenant, db)


# ---------------------------------------------------------------------------
# AI Handling Config
# ---------------------------------------------------------------------------


@router.get(
    "/ai/handling",
    response_model=SuccessResponse[AICallHandlingConfig],
    summary="Get handling config",
    description="Get AI call handling configuration.",
)
async def get_handling_config(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AICallHandlingConfig]:
    """Get AI handling config."""
    config = await _get_or_create_tenant_config(db, tenant.id)
    ai = config.ai_settings or {}
    handling = ai.get("handling", {})

    return SuccessResponse(
        data=AICallHandlingConfig(
            max_call_duration_minutes=handling.get("max_call_duration_minutes", 30),
            enable_call_recording=handling.get("enable_call_recording", True),
            enable_transcript=handling.get("enable_transcript", True),
            take_messages_when=handling.get("take_messages_when", "always"),
            transfer_when=handling.get("transfer_when", "on_request"),
            attempt_human_transfer=handling.get("attempt_human_transfer", True),
            transfer_targets=handling.get("transfer_targets", []),
            custom_instructions=handling.get("custom_instructions"),
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/ai/handling",
    response_model=SuccessResponse[AICallHandlingConfig],
    summary="Update handling config",
    description="Update AI call handling configuration.",
)
async def update_handling_config(
    body: AIHandlingUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AICallHandlingConfig]:
    """Update AI handling configuration."""
    config = await _get_or_create_tenant_config(db, tenant.id)
    ai = dict(config.ai_settings or {})
    handling = dict(ai.get("handling", {}))

    update = body.model_dump(exclude_none=True)
    handling.update(update)
    ai["handling"] = handling
    config.ai_settings = ai

    await db.flush()
    logger.info("ai_handling.updated", tenant_id=str(tenant.id))
    return await get_handling_config(tenant, db)


# ---------------------------------------------------------------------------
# FAQ Routes
# ---------------------------------------------------------------------------


@router.get(
    "/faq",
    response_model=SuccessResponse[FAQListResponse],
    summary="List FAQ",
    description="List FAQ entries with optional category filter and search.",
)
async def list_faq(
    category: str | None = None,
    search: str | None = None,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[FAQListResponse]:
    """List FAQ entries."""
    stmt = select(FAQEntryModel).where(
        FAQEntryModel.tenant_id == tenant.id,
        FAQEntryModel.is_active == True,  # noqa: E712
    )
    if category:
        stmt = stmt.where(FAQEntryModel.category == category)
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            FAQEntryModel.question.ilike(search_pattern)
            | FAQEntryModel.answer.ilike(search_pattern)
        )

    result = await db.execute(stmt)
    faqs = result.scalars().all()

    cat_stmt = (
        select(FAQEntryModel.category)
        .where(
            FAQEntryModel.tenant_id == tenant.id,
            FAQEntryModel.is_active == True,  # noqa: E712
            FAQEntryModel.category.isnot(None),
        )
        .distinct()
    )
    cat_result = await db.execute(cat_stmt)
    categories = sorted([row[0] for row in cat_result.all() if row[0]])

    return SuccessResponse(
        data=FAQListResponse(
            items=[_faq_db_to_schema(f) for f in faqs],
            total=len(faqs),
            categories=categories,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/faq",
    response_model=SuccessResponse[FAQEntry],
    status_code=status.HTTP_201_CREATED,
    summary="Create FAQ",
    description="Create a new FAQ entry.",
)
async def create_faq(
    body: FAQCreateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[FAQEntry]:
    """Create FAQ entry."""
    faq = FAQEntryModel(
        tenant_id=tenant.id,
        question=body.question,
        answer=body.answer,
        category=body.category or "general",
        tags_json=body.tags,
    )
    db.add(faq)
    await db.flush()

    logger.info("faq.created", faq_id=str(faq.id), tenant_id=str(tenant.id))

    return SuccessResponse(
        data=_faq_db_to_schema(faq),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/faq/{faq_id}",
    response_model=SuccessResponse[FAQEntry],
    summary="Get FAQ",
    description="Get a single FAQ entry by ID.",
)
async def get_faq(
    faq_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[FAQEntry]:
    """Get FAQ entry."""
    result = await db.execute(
        select(FAQEntryModel).where(
            FAQEntryModel.id == faq_id,
            FAQEntryModel.tenant_id == tenant.id,
        )
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")

    return SuccessResponse(
        data=_faq_db_to_schema(faq),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/faq/{faq_id}",
    response_model=SuccessResponse[FAQEntry],
    summary="Update FAQ",
    description="Update an FAQ entry.",
)
async def update_faq(
    faq_id: uuid.UUID,
    body: FAQUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[FAQEntry]:
    """Update FAQ entry."""
    result = await db.execute(
        select(FAQEntryModel).where(
            FAQEntryModel.id == faq_id,
            FAQEntryModel.tenant_id == tenant.id,
        )
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")

    if body.question is not None:
        faq.question = body.question
    if body.answer is not None:
        faq.answer = body.answer
    if body.category is not None:
        faq.category = body.category
    if body.tags is not None:
        faq.tags_json = body.tags
    if body.is_active is not None:
        faq.is_active = body.is_active

    await db.flush()
    await db.refresh(faq)

    return SuccessResponse(
        data=_faq_db_to_schema(faq),
        meta=ResponseMeta(request_id=""),
    )


@router.delete(
    "/faq/{faq_id}",
    response_model=SuccessResponse[dict],
    summary="Delete FAQ",
    description="Delete an FAQ entry.",
)
async def delete_faq(
    faq_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Delete FAQ entry."""
    result = await db.execute(
        select(FAQEntryModel).where(
            FAQEntryModel.id == faq_id,
            FAQEntryModel.tenant_id == tenant.id,
        )
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")

    await db.delete(faq)
    await db.flush()

    return SuccessResponse(
        data={"message": "FAQ deleted successfully"},
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/faq/import",
    response_model=SuccessResponse[dict],
    summary="Bulk import FAQ",
    description="Bulk import FAQ entries. Optionally replace existing.",
)
async def bulk_import_faq(
    body: FAQBulkImportRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Bulk import FAQ entries."""
    if body.replace_existing:
        await db.execute(
            sa_delete(FAQEntryModel).where(FAQEntryModel.tenant_id == tenant.id)
        )

    imported = 0
    for entry in body.entries:
        faq = FAQEntryModel(
            tenant_id=tenant.id,
            question=entry.question,
            answer=entry.answer,
            category=entry.category or "general",
            tags_json=entry.tags,
        )
        db.add(faq)
        imported += 1

    await db.flush()

    logger.info("faq.imported", tenant_id=str(tenant.id), count=imported)

    return SuccessResponse(
        data={
            "message": f"Successfully imported {imported} FAQ entries",
            "imported_count": imported,
            "replaced": body.replace_existing,
        },
        meta=ResponseMeta(request_id=""),
    )


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


@router.get(
    "/routing",
    response_model=SuccessResponse[list[RoutingRule]],
    summary="Get routing rules",
    description="Get call routing rules for the business.",
)
async def get_routing_rules(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[RoutingRule]]:
    """Get routing rules."""
    config = await _get_or_create_tenant_config(db, tenant.id)
    rules_data = config.routing_rules or []

    rules = []
    for r in rules_data:
        rules.append(
            RoutingRule(
                id=uuid.UUID(r["id"]) if "id" in r else uuid.uuid4(),
                tenant_id=tenant.id,
                name=r["name"],
                condition=r["condition"],
                action=r["action"],
                priority=r.get("priority", 0),
                is_active=r.get("is_active", True),
                created_at=(
                    datetime.fromisoformat(r["created_at"])
                    if r.get("created_at")
                    else datetime.utcnow()
                ),
                updated_at=(
                    datetime.fromisoformat(r["updated_at"])
                    if r.get("updated_at")
                    else None
                ),
            )
        )

    return SuccessResponse(data=rules, meta=ResponseMeta(request_id=""))


@router.put(
    "/routing",
    response_model=SuccessResponse[list[RoutingRule]],
    summary="Update routing rules",
    description="Update call routing rules.",
)
async def update_routing_rules(
    body: RoutingRuleUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[RoutingRule]]:
    """Update routing rules."""
    config = await _get_or_create_tenant_config(db, tenant.id)

    now = datetime.utcnow().isoformat()
    rules = []
    for r in body.rules:
        rule = {
            "id": r.get("id", str(uuid.uuid4())),
            "tenant_id": str(tenant.id),
            "name": r["name"],
            "condition": r["condition"],
            "action": r["action"],
            "priority": r.get("priority", 0),
            "is_active": r.get("is_active", True),
            "created_at": now,
            "updated_at": now,
        }
        rules.append(rule)

    config.routing_rules = rules
    await db.flush()

    logger.info("routing.updated", tenant_id=str(tenant.id), rule_count=len(rules))

    return await get_routing_rules(tenant, db)


# ---------------------------------------------------------------------------
# Script version history (server-side, synced to dashboard editors)
# ---------------------------------------------------------------------------


class ScriptVersionCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    label: str | None = Field(default=None, max_length=64)


@router.get(
    "/scripts/{script_key}/versions",
    response_model=SuccessResponse[list[dict[str, Any]]],
    summary="List script versions",
    description="Version history for a greeting/script key (server-persisted).",
)
async def get_script_versions(
    script_key: str,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[dict[str, Any]]]:
    config = await _get_or_create_tenant_config(db, tenant.id)
    ai = dict(config.ai_settings or {})
    versions = list_script_versions(ai, script_key)
    return SuccessResponse(data=versions, meta=ResponseMeta(request_id=""))


@router.post(
    "/scripts/{script_key}/versions",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Save script version",
    description="Append a new script version for rollback and RAG indexing.",
)
async def save_script_version(
    script_key: str,
    body: ScriptVersionCreate,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict[str, Any]]:
    config = await _get_or_create_tenant_config(db, tenant.id)
    ai = dict(config.ai_settings or {})
    ai, version = append_script_version(
        ai,
        script_key=script_key,
        content=body.content,
        label=body.label,
    )
    config.ai_settings = ai
    await db.flush()
    logger.info(
        "script_version.saved",
        tenant_id=str(tenant.id),
        script_key=script_key,
        version_id=version.get("id"),
    )
    return SuccessResponse(data=version, meta=ResponseMeta(request_id=""))
