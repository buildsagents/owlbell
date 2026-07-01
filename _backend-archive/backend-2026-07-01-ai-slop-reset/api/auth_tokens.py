"""api/auth_tokens.py - Single source of truth for JWT signing & verification.

Both the auth routes (signing) and the auth middleware + dependencies (verifying)
import from here, so a token minted at login is always verifiable by the same
process. Secret + algorithm come from settings (``SECURITY_JWT_SECRET`` /
``SECURITY_JWT_ALGORITHM``); in dev the secret is a stable per-process random value.

Replaces the previously hardcoded ``JWT_SECRET = "change-me-in-production"`` that was
duplicated across auth.py and middleware.py.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from backend.config import get_settings


def _secret() -> str:
    s = get_settings().security.jwt_secret
    return s.get_secret_value() if hasattr(s, "get_secret_value") else str(s)


def _alg() -> str:
    return get_settings().security.jwt_algorithm or "HS256"


def _access_ttl() -> timedelta:
    return timedelta(minutes=get_settings().security.jwt_access_token_ttl_minutes)


def _refresh_ttl() -> timedelta:
    return timedelta(days=get_settings().security.jwt_refresh_token_ttl_days)


def create_access_token(user_id: Any, tenant_id: Any, role: str, email: str) -> str:
    """Mint a signed access token carrying the user + tenant claims."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + _access_ttl(),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=_alg())


def create_refresh_token(user_id: Any) -> str:
    """Mint a signed refresh token with a unique JTI."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": secrets.token_urlsafe(32),
        "iat": now,
        "exp": now + _refresh_ttl(),
    }
    return jwt.encode(payload, _secret(), algorithm=_alg())


def decode_token(token: str) -> dict[str, Any]:
    """Verify a token's signature + expiry and return its claims.

    Raises ``jwt.PyJWTError`` (e.g. ExpiredSignatureError, InvalidTokenError) on
    any failure — callers should catch and translate to 401.
    """
    return jwt.decode(token, _secret(), algorithms=[_alg()])
