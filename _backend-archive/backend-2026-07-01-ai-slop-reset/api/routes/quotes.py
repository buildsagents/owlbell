"""api/routes/quotes.py - Customer quote CRUD + status transitions.

Owners (or their field-service tool via the API) record quotes here; the
quote-follow-up worker chases the ones left in ``sent``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, CurrentUser, DBSession
from api.schemas.base import ResponseMeta, SuccessResponse
from backend.business.quotes.service import QuoteService
from backend.db.models.business import Quote
from backend.db.models.enums import QuoteStatus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/quotes", tags=["Quotes"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QuoteCreateRequest(BaseModel):
    customer_phone: str = Field(..., max_length=30)
    customer_name: Optional[str] = Field(default=None, max_length=255)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    title: str = Field(default="Quote", max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    amount: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="GBP", max_length=3)
    call_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None


class QuoteStatusUpdateRequest(BaseModel):
    status: QuoteStatus


class QuoteRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    status: QuoteStatus
    customer_phone: str
    customer_name: Optional[str]
    customer_email: Optional[str]
    title: str
    description: Optional[str]
    amount: Optional[float]
    currency: str
    sent_at: Optional[datetime]
    accepted_at: Optional[datetime]
    declined_at: Optional[datetime]
    expires_at: Optional[datetime]
    last_followup_at: Optional[datetime]
    followup_count: int
    created_at: datetime
    updated_at: datetime


def _to_record(q: Quote) -> QuoteRecord:
    return QuoteRecord(
        id=q.id,
        tenant_id=q.tenant_id,
        status=q.status,
        customer_phone=q.customer_number,
        customer_name=q.customer_name,
        customer_email=q.customer_email,
        title=q.title,
        description=q.description,
        amount=float(q.amount) if q.amount is not None else None,
        currency=q.currency,
        sent_at=q.sent_at,
        accepted_at=q.accepted_at,
        declined_at=q.declined_at,
        expires_at=q.expires_at,
        last_followup_at=q.last_followup_at,
        followup_count=q.followup_count,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SuccessResponse[QuoteRecord],
    status_code=http_status.HTTP_201_CREATED,
    summary="Create quote",
)
async def create_quote(
    body: QuoteCreateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[QuoteRecord]:
    data: dict[str, Any] = {
        "tenant_id": tenant.id,
        "call_id": body.call_id,
        "customer_number": body.customer_phone,
        "customer_name": body.customer_name,
        "customer_email": body.customer_email,
        "title": body.title,
        "description": body.description,
        "amount": Decimal(str(body.amount)) if body.amount is not None else None,
        "currency": body.currency,
        "status": QuoteStatus.SENT,
        "expires_at": body.expires_at,
    }
    svc = QuoteService(db, tenant.id)
    quote = await svc.create_quote(data)
    await db.refresh(quote)
    return SuccessResponse(data=_to_record(quote), meta=ResponseMeta(request_id=""))


@router.get(
    "",
    response_model=SuccessResponse[list[QuoteRecord]],
    summary="List quotes",
)
async def list_quotes(
    status: Optional[QuoteStatus] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[QuoteRecord]]:
    svc = QuoteService(db, tenant.id)
    quotes = await svc.list_quotes(status=status, limit=limit, offset=offset)
    return SuccessResponse(
        data=[_to_record(q) for q in quotes], meta=ResponseMeta(request_id="")
    )


@router.get(
    "/{quote_id}",
    response_model=SuccessResponse[QuoteRecord],
    summary="Get quote",
)
async def get_quote(
    quote_id: UUID,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[QuoteRecord]:
    svc = QuoteService(db, tenant.id)
    try:
        quote = await svc.get_quote(quote_id)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )
    return SuccessResponse(data=_to_record(quote), meta=ResponseMeta(request_id=""))


@router.patch(
    "/{quote_id}/status",
    response_model=SuccessResponse[QuoteRecord],
    summary="Update quote status",
)
async def update_quote_status(
    quote_id: UUID,
    body: QuoteStatusUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[QuoteRecord]:
    svc = QuoteService(db, tenant.id)
    try:
        quote = await svc.set_status(quote_id, body.status)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )
    return SuccessResponse(data=_to_record(quote), meta=ResponseMeta(request_id=""))
