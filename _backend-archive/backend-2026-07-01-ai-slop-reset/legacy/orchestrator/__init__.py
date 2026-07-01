"""
Agent Orchestration & Scaling package for Owlbell.

Lazy exports avoid circular imports when submodules are imported directly
(e.g. tests/e2e/conftest importing event_bus before __init__ finishes).
"""

from __future__ import annotations

__version__ = "1.0.0"

_LAZY_EXPORTS = {
    "CircuitBreaker": ("legacy.orchestrator.circuit_breaker", "CircuitBreaker"),
    "CircuitBreakerOpen": ("legacy.orchestrator.circuit_breaker", "CircuitBreakerOpen"),
    "CircuitState": ("legacy.orchestrator.circuit_breaker", "CircuitState"),
    "get_circuit_breaker": ("legacy.orchestrator.circuit_breaker", "get_circuit_breaker"),
    "reset_all_circuits": ("legacy.orchestrator.circuit_breaker", "reset_all_circuits"),
    "reset_all_circuits_async": ("legacy.orchestrator.circuit_breaker", "reset_all_circuits_async"),
    "EventBus": ("legacy.orchestrator.event_bus", "EventBus"),
    "GatewayRouter": ("legacy.orchestrator.gateway", "GatewayRouter"),
    "create_orchestrator_router": ("legacy.orchestrator.gateway", "create_orchestrator_router"),
    "HealthMonitor": ("legacy.orchestrator.health_monitor", "HealthMonitor"),
    "LoadBalancer": ("legacy.orchestrator.load_balancer", "LoadBalancer"),
    "ActiveSession": ("legacy.orchestrator.models", "ActiveSession"),
    "CallState": ("legacy.orchestrator.models", "CallState"),
    "EventType": ("legacy.orchestrator.models", "EventType"),
    "QueuePriority": ("legacy.orchestrator.models", "QueuePriority"),
    "QueuedCall": ("legacy.orchestrator.models", "QueuedCall"),
    "SystemEvent": ("legacy.orchestrator.models", "SystemEvent"),
    "WorkerNode": ("legacy.orchestrator.models", "WorkerNode"),
    "WorkerStatus": ("legacy.orchestrator.models", "WorkerStatus"),
    "SessionManager": ("legacy.orchestrator.session_manager", "SessionManager"),
    "WorkerPool": ("legacy.orchestrator.worker_pool", "WorkerPool"),
    "CallQueue": ("legacy.orchestrator.call_queue", "CallQueue"),
}

__all__ = list(_LAZY_EXPORTS.keys()) + ["__version__"]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module_path, attr = _LAZY_EXPORTS[name]
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")