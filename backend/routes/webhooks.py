"""Webhook placeholders for integrations."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/retell")
async def retell_webhook(request: Request) -> dict:
    payload = await request.json()
    return {"received": True, "provider": "retell", "event": payload.get("event")}


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.json()
    return {"received": True, "provider": "stripe", "type": payload.get("type")}
