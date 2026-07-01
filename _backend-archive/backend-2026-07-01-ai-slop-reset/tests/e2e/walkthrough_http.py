"""Shared HTTP helpers for API walkthrough e2e tests."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest_asyncio

from api.auth_tokens import create_access_token
from backend.app_factory import create_app, lifespan

BASE_URL = "http://testserver"
API_PREFIX = "/api/v1"


def create_test_app():
    return create_app(env="testing")


def _make_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=BASE_URL,
        timeout=httpx.Timeout(30.0),
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def running_app():
    """Session-scoped app with lifespan — avoids per-test startup cost."""
    app = create_test_app()
    async with lifespan(app):
        yield app


async def seed_calls_for_tenant(tenant_id: uuid.UUID, count: int = 3) -> None:
    """Insert call rows for walkthrough tests (uses the running app's DB pool)."""
    from decimal import Decimal

    from backend.db.models.call import Call, Recording
    from backend.db.models.enums import CallDirection, CallStatus
    from backend.db.session import get_session_maker

    session_maker = get_session_maker()
    session = session_maker()
    try:
        now = datetime.utcnow()
        for i in range(count):
            call_id = uuid.uuid4()
            session.add(
                Call(
                    id=call_id,
                    tenant_id=tenant_id,
                    call_sid=f"CA-WALK-{tenant_id.hex[:8]}-{i}",
                    direction=CallDirection.INBOUND,
                    caller_number="+15550001111",
                    destination_number="+15559998888",
                    status=CallStatus.COMPLETED,
                    started_at=now - timedelta(hours=i + 1),
                    duration_seconds=60,
                )
            )
            if i == 0:
                session.add(
                    Recording(
                        tenant_id=tenant_id,
                        call_id=call_id,
                        file_path=f"recordings/{call_id}.wav",
                        file_size_bytes=1024,
                        duration_seconds=Decimal("60.0"),
                        access_url="https://example.com/rec.mp3",
                    )
                )
        await session.commit()
    finally:
        await session.close()


@asynccontextmanager
async def app_client(app=None):
    """Yield an httpx client; uses session ``running_app`` when app is None."""
    if app is None:
        app = create_test_app()
        async with lifespan(app):
            async with _make_client(app) as client:
                yield client
    else:
        async with _make_client(app) as client:
            yield client


async def register_user(client: httpx.AsyncClient, email: str | None = None) -> httpx.Response:
    payload = {
        "email": email or f"e2e_{uuid.uuid4().hex[:8]}@example.com",
        "password": "SecurePass123!",
        "business_name": "Walkthrough Business",
        "phone_number": "+15551234567",
        "timezone": "America/New_York",
    }
    return await client.post(f"{API_PREFIX}/auth/register", json=payload)


async def authed_client_from(app=None) -> httpx.AsyncClient:
    """Context-less helper: returns client with Bearer token set (caller must close)."""
    cm = app_client(app)
    client = await cm.__aenter__()
    resp = await register_user(client)
    if resp.status_code != 201:
        await cm.__aexit__(None, None, None)
        raise RuntimeError(f"register failed: {resp.status_code} {resp.text}")
    token = resp.json()["data"]["tokens"]["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def set_super_admin_token(client: httpx.AsyncClient, reg_data: dict[str, Any]) -> None:
    token = create_access_token(
        uuid.UUID(reg_data["user"]["id"]),
        uuid.UUID(reg_data["tenant"]["id"]),
        "super_admin",
        reg_data["user"]["email"],
    )
    client.headers["Authorization"] = f"Bearer {token}"


@asynccontextmanager
async def authed_app_client(app=None, *, seed_calls: int = 0):
    async with app_client(app) as client:
        resp = await register_user(client)
        if resp.status_code != 201:
            raise RuntimeError(f"register failed: {resp.status_code} {resp.text}")
        token = resp.json()["data"]["tokens"]["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        if seed_calls > 0:
            tenant_id = uuid.UUID(resp.json()["data"]["tenant"]["id"])
            await seed_calls_for_tenant(tenant_id, seed_calls)
        yield client


@asynccontextmanager
async def super_admin_app_client(app=None):
    async with app_client(app) as client:
        resp = await register_user(client)
        if resp.status_code != 201:
            raise RuntimeError(f"register failed: {resp.status_code} {resp.text}")
        set_super_admin_token(client, resp.json()["data"])
        yield client