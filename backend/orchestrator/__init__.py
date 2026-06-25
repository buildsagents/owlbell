"""
Agent Orchestration & Scaling package for Owlbell.

This package manages the lifecycle of simultaneous AI phone calls --
from SIP INVITE to final BYE. It handles call queuing, AI worker
assignment, real-time audio streaming, session state management,
health monitoring, and graceful degradation under load.

Components:
- Gateway: FastAPI WebSocket + HTTP gateway
- SessionManager: Redis-backed session state machine
- EventBus: Redis pub/sub + Streams event bus
- WorkerPool: Celery worker pool with auto-scaling
- CallQueue: Priority call queue with wait time estimation
- HealthMonitor: Health monitoring with auto-recovery
- LoadBalancer: GPU-aware load balancing
- CircuitBreaker: Distributed circuit breaker pattern
- Tasks: Celery task definitions
"""

__version__ = "1.0.0"

from backend.orchestrator.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    get_circuit_breaker,
    reset_all_circuits,
    reset_all_circuits_async,
)
from backend.orchestrator.event_bus import EventBus
from backend.orchestrator.gateway import GatewayRouter, create_orchestrator_router
from backend.orchestrator.health_monitor import HealthMonitor
from backend.orchestrator.load_balancer import LoadBalancer
from backend.orchestrator.models import (
    ActiveSession,
    CallState,
    EventType,
    QueuePriority,
    QueuedCall,
    SystemEvent,
    WorkerNode,
    WorkerStatus,
)
from backend.orchestrator.session_manager import SessionManager
from backend.orchestrator.worker_pool import WorkerPool

__all__ = [
    # Core classes
    "SessionManager",
    "WorkerPool",
    "EventBus",
    "CallQueue",
    "LoadBalancer",
    "HealthMonitor",
    "GatewayRouter",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    # Models
    "ActiveSession",
    "WorkerNode",
    "QueuedCall",
    "SystemEvent",
    # Enums
    "CallState",
    "WorkerStatus",
    "QueuePriority",
    "EventType",
    "CircuitState",
    # Functions
    "create_orchestrator_router",
    "get_circuit_breaker",
    "reset_all_circuits",
    "reset_all_circuits_async",
    # Version
    "__version__",
]

# Import CallQueue here to avoid circular import issues
try:
    from backend.orchestrator.call_queue import CallQueue
    __all__.append("CallQueue")
except ImportError:
    pass
