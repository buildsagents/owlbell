"""Centralized dependency injection for Owlbell application services."""

from backend.di.container import (
    DependencyContainer,
    get_container,
    reset_container,
    set_container,
)
from backend.di.contexts import AIPipelineContext, CallManagerContext

__all__ = [
    "AIPipelineContext",
    "CallManagerContext",
    "DependencyContainer",
    "get_container",
    "reset_container",
    "set_container",
]