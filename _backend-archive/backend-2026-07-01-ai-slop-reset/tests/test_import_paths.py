"""Guard: import roots must work regardless of pytest invocation cwd."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from tests._path_bootstrap import BACKEND_DIR, PROJECT_ROOT, ensure_test_import_paths

_SESSION_FACTORY_NAMES = frozenset({
    "dispose_engine",
    "get_engine",
    "get_session_maker",
    "init_engine",
    "open_db_session",
    "require_session_maker",
})
_FORBIDDEN_SESSION_IMPORT_MODULES = frozenset({
    "api.dependencies",
    "backend.dependencies",
})


def test_import_paths_are_absolute():
    project, backend = ensure_test_import_paths()
    assert project == PROJECT_ROOT
    assert backend == BACKEND_DIR
    assert PROJECT_ROOT in sys.path
    assert BACKEND_DIR in sys.path


def test_backend_and_api_packages_importable():
    ensure_test_import_paths()
    import backend.config  # noqa: F401
    import api.dependencies  # noqa: F401


def test_session_factory_lives_in_backend_db_session_not_api_dependencies():
    """Session factory is canonical in backend.db.session (not api or backend.dependencies)."""
    ensure_test_import_paths()
    from backend.db import get_session_maker as pkg_get_session_maker
    from backend.db.session import get_session_maker, require_session_maker

    assert callable(get_session_maker)
    assert callable(require_session_maker)
    assert callable(pkg_get_session_maker)
    assert get_session_maker is pkg_get_session_maker

    import api.dependencies as api_deps
    import backend.dependencies as svc_deps

    assert not hasattr(api_deps, "get_session_maker")
    assert not hasattr(api_deps, "require_session_maker")
    assert not hasattr(svc_deps, "get_session_maker")
    assert not hasattr(svc_deps, "require_session_maker")


def test_backend_dependencies_is_service_layer_not_route_di():
    """backend.dependencies must not duplicate FastAPI auth/tenant DI."""
    ensure_test_import_paths()
    import backend.dependencies as svc
    from backend.di import DependencyContainer, get_container

    assert hasattr(svc, "get_ai_pipeline")
    assert hasattr(svc, "get_usage_tracker")
    assert not hasattr(svc, "get_current_user")
    assert not hasattr(svc, "get_current_tenant")
    assert not hasattr(svc, "UserContext")
    assert callable(get_container)
    assert DependencyContainer.__name__ == "DependencyContainer"


def test_operations_tenant_package_importable():
    """Tenant manager/middleware must load without TenantMiddleware name errors."""
    ensure_test_import_paths()
    from backend.operations.tenant import TenantManager, TenantMiddleware

    assert TenantManager.__name__ == "TenantManager"
    assert TenantMiddleware.__name__ == "TenantResolutionMiddleware"
    # Importing manager must not re-trigger a broken package __init__
    import operations.tenant.manager  # noqa: F401


def test_worker_modules_importable_with_cwd_only():
    """Celery workers bootstrap import paths from backend/ cwd."""
    ensure_test_import_paths()
    import workers.celery_app  # noqa: F401
    import workers.onboarding_tasks  # noqa: F401
    import workers.analytics_tasks  # noqa: F401

    from backend.domain.analytics.rollup import rollup_all_tenants_for_day
    from backend.domain.onboarding.orchestrator import get_orchestrator

    assert callable(rollup_all_tenants_for_day)
    assert callable(get_orchestrator)


def test_no_session_factory_imports_from_api_or_service_dependencies() -> None:
    """Session factory must be imported from backend.db.session, never re-export layers."""
    backend_root = Path(BACKEND_DIR)
    violations: list[str] = []

    for path in backend_root.rglob("*.py"):
        if any(part in path.parts for part in ("tests", "htmlcov", ".venv")):
            continue
        if path.name == "dependencies.py" and path.parent.name in ("api", "backend"):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module not in _FORBIDDEN_SESSION_IMPORT_MODULES:
                continue
            for alias in node.names:
                if alias.name in _SESSION_FACTORY_NAMES:
                    rel = path.relative_to(backend_root)
                    violations.append(f"{rel}: from {node.module} import {alias.name}")

    assert not violations, "Forbidden session factory imports:\n" + "\n".join(violations)


def test_create_app_registers_api_routers_without_session_import_error(postgres_env) -> None:
    """Regression: api router import must not fail on get_session_maker re-exports."""
    from backend.app_factory import create_app

    app = create_app(env="testing")
    route_paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/onboarding/intake" in route_paths
    assert "/health" in route_paths


def test_chained_domain_import_without_pythonpath():
    """Chained domain imports work via editable install, not manual PYTHONPATH."""
    import os

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    code = """
import backend
from backend.domain.onboarding.orchestrator import get_orchestrator
from backend.domain.analytics.rollup import rollup_all_tenants_for_day
assert callable(get_orchestrator)
assert callable(rollup_all_tenants_for_day)
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout