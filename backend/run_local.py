"""
Local zero-infrastructure launcher for the Owlbell backend.

Starts a self-contained bundled PostgreSQL (via ``pgserver``), uses an
in-process ``fakeredis`` for cache/pub-sub, creates all tables, then serves
the FastAPI app with uvicorn — all in a single process, no Docker required.

Usage:
    .venv/Scripts/python.exe run_local.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# 1. Import paths: both project root (for ``backend.*``) and the backend dir
#    (for bare ``api.*`` / ``orchestrator.*`` imports used across the codebase).
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
for _p in (PROJECT_ROOT, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# 2. Start the bundled PostgreSQL server (persists for this process lifetime).
# ---------------------------------------------------------------------------
import pgserver  # noqa: E402

PGDATA = os.path.join(BACKEND_DIR, ".pgdata")
print(f"[run_local] Starting bundled PostgreSQL (data dir: {PGDATA}) ...")
server = pgserver.get_server(PGDATA)  # kept alive while this process runs
_uri = urlparse(server.get_uri())
print(f"[run_local] PostgreSQL ready on {_uri.hostname}:{_uri.port}")

# ---------------------------------------------------------------------------
# 3. Configure the backend via environment (read by backend/config.py).
# ---------------------------------------------------------------------------
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_DEBUG", "true")  # enables /docs + /openapi.json
os.environ["POSTGRES_HOST"] = _uri.hostname or "127.0.0.1"
os.environ["POSTGRES_PORT"] = str(_uri.port or 5432)
os.environ["POSTGRES_USER"] = _uri.username or "postgres"
os.environ["POSTGRES_PASSWORD"] = _uri.password or ""
os.environ["POSTGRES_DB"] = (_uri.path or "/postgres").lstrip("/") or "postgres"
os.environ["USE_FAKE_REDIS"] = "1"
os.environ["FEATURE_ENABLE_AI_GREETING"] = "false"  # skip heavy STT/LLM/TTS stack locally
os.environ.setdefault("APP_SECRET_KEY", "dev-secret-not-for-production-0123456789abcdef0123456789")
os.environ.setdefault("JWT_SECRET_KEY", "dev-jwt-not-for-production-0123456789abcdef0123456789")
os.environ.setdefault(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

_DB_URL = (
    f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
)


# ---------------------------------------------------------------------------
# 4. Create all tables from the SQLAlchemy metadata.
# ---------------------------------------------------------------------------
async def _create_tables() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.db.models import Base  # registers all models on Base.metadata

    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


print("[run_local] Creating database tables ...")
asyncio.run(_create_tables())
print("[run_local] Schema ready.")

# ---------------------------------------------------------------------------
# 5. Serve the API (single process so pgserver + env stay live).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    print("[run_local] Starting API on http://0.0.0.0:8000 ...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
