"""Top-level pytest configuration for backend tests."""

from __future__ import annotations

import pytest

# Requires editable install: pip install -e .  (adds import roots via .pth)
import backend  # noqa: F401

pytest_plugins = ["pytest_asyncio", "tests.e2e.walkthrough_http"]

from tests.postgres_bootstrap import bootstrap_postgres, close_session_loop


@pytest.fixture(scope="session")
def postgres_env():
    """Start embedded PostgreSQL (pgserver) and configure test environment."""
    env = bootstrap_postgres()
    yield env
    close_session_loop()


@pytest.fixture(scope="session")
def postgres_db(postgres_env):
    """Alias for tests that declare an explicit Postgres dependency."""
    return postgres_env


@pytest.fixture(autouse=True)
def _ensure_postgres_env(request):
    """Unit tests skip embedded Postgres; integration/e2e tests use pgserver."""
    if request.node.get_closest_marker("unit") is not None:
        yield
        return
    env = request.getfixturevalue("postgres_env")
    from workers.db import ensure_worker_db

    ensure_worker_db()
    yield


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when pgserver is unavailable (common on Windows CI hosts)."""
    try:
        import pgserver  # noqa: F401
    except ImportError:
        skip = pytest.mark.skip(reason="pgserver not installed")
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip)