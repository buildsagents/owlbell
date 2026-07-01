"""Guard: centralized DI container owns app service singletons."""

from __future__ import annotations

import pytest

from backend.di import (
    DependencyContainer,
    get_container,
    reset_container,
    set_container,
)


@pytest.fixture(autouse=True)
def _isolate_container():
    reset_container()
    yield
    reset_container()


def test_get_container_returns_singleton() -> None:
    a = get_container()
    b = get_container()
    assert a is b
    assert isinstance(a, DependencyContainer)


def test_set_container_replaces_singleton() -> None:
    original = get_container()
    replacement = DependencyContainer()
    set_container(replacement)
    assert get_container() is replacement
    assert get_container() is not original


@pytest.mark.asyncio
async def test_container_startup_and_shutdown(postgres_env) -> None:
    from backend.config import get_settings

    container = DependencyContainer()
    set_container(container)

    settings = get_settings()
    await container.startup(settings)
    assert container.started is True

    tracker = await container.usage_tracker()
    assert tracker is not None
    assert await container.usage_tracker() is tracker

    await container.shutdown()
    assert container.started is False


def test_backend_dependencies_delegate_to_container() -> None:
    import backend.dependencies as deps

    assert hasattr(deps, "get_usage_tracker")
    assert hasattr(deps, "get_prompt_manager")
    assert hasattr(deps, "close_all_dependencies")


def test_create_app_attaches_container_to_state(postgres_env) -> None:
    from backend.app_factory import create_app

    app = create_app(env="testing")
    assert hasattr(app.state, "container")
    assert isinstance(app.state.container, DependencyContainer)
    assert app.state.container is get_container()