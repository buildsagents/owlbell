"""
health_monitor.py -- System health monitoring and auto-recovery.

Responsibilities:
- Track worker heartbeats and detect failures
- Monitor GPU utilization and temperature
- Detect system overload conditions
- Trigger auto-recovery (restart failed workers)
- Generate Prometheus-compatible metrics
- Track degradation state
- Provide system status overview

Health Check Strategy:
- Workers send heartbeat every 2 seconds via Redis SET with 10s TTL
- If heartbeat not received for 6 seconds (3 missed), worker marked UNHEALTHY
- If heartbeat not received for 30 seconds, worker marked OFFLINE
- Failed workers trigger: session reassignment + container restart
- GPU OOM events trigger: emergency session evacuation

Integration Points:
- IN: WorkerPool (worker status changes)
- IN: Redis (heartbeat keys, metrics)
- IN: Celery beat (periodic checks)
- OUT: EventBus (health events)
- OUT: WorkerPool (restart commands)
- OUT: SessionManager (session reassignment)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from orchestrator.models import (
    ActiveSession,
    CallState,
    EventType,
    SystemEvent,
    WorkerNode,
    WorkerStatus,
)

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors system health and triggers auto-recovery.

    Tracks worker heartbeats, GPU metrics, and system capacity.
    Automatically restarts failed workers and manages degradation.

    Redis key patterns:
    - ``heartbeat:{worker_id}`` -> HASH (latest heartbeat data)
    - ``metrics:gpu:{device}:utilization`` -> STRING
    - ``metrics:gpu:{device}:memory_used`` -> STRING
    - ``metrics:gpu:{device}:temperature`` -> STRING
    - ``system:degradation:mode`` -> STRING
    - ``system:degradation:since`` -> STRING
    """

    # Health check thresholds
    HEARTBEAT_INTERVAL: int = 2
    HEARTBEAT_MISS_THRESHOLD: int = 3
    OFFLINE_THRESHOLD: int = 15

    # GPU thresholds
    GPU_UTIL_HIGH: float = 90.0
    GPU_TEMP_HIGH: float = 85.0
    GPU_TEMP_CRITICAL: float = 95.0
    GPU_MEMORY_CRITICAL: float = 95.0

    # System thresholds
    OVERLOAD_SESSION_RATIO: float = 0.95
    DEGRADATION_TRIGGER: float = 0.90
    RECOVERY_THRESHOLD: float = 0.70

    # Recovery settings
    AUTO_RESTART_ENABLED: bool = True
    RESTART_COOLDOWN: int = 60
    MAX_RESTART_ATTEMPTS: int = 3

    # Metrics prefix
    METRIC_PREFIX: str = "answerflow"

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        worker_pool: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        redis_url: str = "redis://localhost:6379/0",
    ):
        self.redis_url = redis_url
        self._redis: Optional[Any] = redis_client
        self.event_bus = event_bus
        self.worker_pool = worker_pool
        self.session_mgr = session_manager

        # Track restart attempts to prevent restart loops
        self._restart_history: Dict[str, List[datetime]] = {}

        # Degradation state
        self._degradation_active: bool = False
        self._degradation_mode: str = "none"
        self._degradation_since: Optional[datetime] = None

    def _get_client(self) -> Any:
        """Get or create async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis

    # ---- Heartbeat Processing ----

    async def record_heartbeat(
        self, worker_id: str, metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record worker heartbeat.

        Called by workers via the /health/heartbeat endpoint.

        Args:
            worker_id: Worker identifier
            metrics: Dict with cpu, memory, GPU metrics

        Returns:
            Dict with acknowledged status and any commands for worker
        """
        client = self._get_client()
        key = f"heartbeat:{worker_id}"
        timestamp = datetime.utcnow().isoformat()

        # Store heartbeat with TTL
        heartbeat_data = {
            "timestamp": timestamp,
            "cpu_percent": str(metrics.get("cpu_percent", 0)),
            "memory_percent": str(metrics.get("memory_percent", 0)),
            "gpu_utilization": str(metrics.get("gpu_utilization", 0)),
            "gpu_memory_used": str(metrics.get("gpu_memory_used", 0)),
            "gpu_temperature": str(metrics.get("gpu_temperature", 0)),
            "inference_latency_ms": str(
                metrics.get("inference_latency_ms", 0)
            ),
            "current_sessions": str(metrics.get("current_sessions", 0)),
        }

        await client.hset(key, mapping=heartbeat_data)
        ttl = getattr(self.worker_pool, "HEARTBEAT_TTL", 10) if self.worker_pool else 10
        await client.expire(key, ttl)

        # Update worker pool record
        if self.worker_pool:
            try:
                await self.worker_pool.heartbeat(worker_id, metrics)
            except Exception as e:
                logger.warning(f"Worker pool heartbeat update failed: {e}")

        # Check for commands pending for this worker
        commands = await self._get_pending_commands(worker_id)

        return {
            "acknowledged": True,
            "timestamp": timestamp,
            "commands": commands,
        }

    async def _get_pending_commands(self, worker_id: str) -> List[Dict[str, Any]]:
        """Get any pending commands for a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            List of command dicts
        """
        client = self._get_client()
        key = f"worker:{worker_id}:commands"
        commands_json = await client.lrange(key, 0, -1)
        if commands_json:
            await client.delete(key)
        return [json.loads(c) for c in commands_json if c]

    async def send_command(
        self, worker_id: str, command: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a command to a worker via Redis list.

        Args:
            worker_id: Worker identifier
            command: Command string
            params: Optional command parameters
        """
        client = self._get_client()
        key = f"worker:{worker_id}:commands"
        cmd = {
            "command": command,
            "params": params or {},
            "sent_at": datetime.utcnow().isoformat(),
        }
        await client.rpush(key, json.dumps(cmd))

    # ---- Health Checks ----

    async def check_all_workers(self) -> Dict[str, Any]:
        """Check health of all workers.

        Called periodically by Celery beat task (every 10 seconds).

        Returns:
            Dict with healthy, unhealthy, and offline worker lists
        """
        if not self.worker_pool:
            return {"error": "Worker pool not configured"}

        workers = await self.worker_pool.list_workers()
        now = datetime.utcnow()

        healthy: List[str] = []
        unhealthy: List[str] = []
        offline: List[str] = []
        restarted: List[str] = []

        for worker in workers:
            # Calculate time since last heartbeat
            last_hb = worker.last_heartbeat_at
            seconds_since_hb = (now - last_hb).total_seconds()

            if seconds_since_hb > self.OFFLINE_THRESHOLD:
                # Worker is OFFLINE
                if worker.status != WorkerStatus.OFFLINE:
                    await self._mark_offline(worker)
                offline.append(worker.worker_id)

                # Reassign sessions if any
                if self.session_mgr and worker.current_sessions:
                    try:
                        reassigned = await self.session_mgr.reassign_calls(
                            worker.worker_id
                        )
                        logger.warning(
                            f"Reassigned {reassigned} calls from offline "
                            f"worker {worker.worker_id}"
                        )
                    except Exception as e:
                        logger.error(f"Session reassignment failed: {e}")

                # Attempt restart (with rate limiting)
                if await self._can_restart(worker.worker_id):
                    try:
                        result = await self.worker_pool.restart_worker(
                            worker.worker_id
                        )
                        restarted.append(worker.worker_id)
                        self._record_restart(worker.worker_id)
                    except Exception as e:
                        logger.error(f"Worker restart failed: {e}")

            elif seconds_since_hb > (
                self.HEARTBEAT_INTERVAL * self.HEARTBEAT_MISS_THRESHOLD
            ):
                # Worker is UNHEALTHY
                if worker.status != WorkerStatus.UNHEALTHY:
                    await self._mark_unhealthy(worker)
                unhealthy.append(worker.worker_id)

                # Attempt recovery
                if await self._can_restart(worker.worker_id):
                    try:
                        result = await self.worker_pool.restart_worker(
                            worker.worker_id
                        )
                        restarted.append(worker.worker_id)
                        self._record_restart(worker.worker_id)
                    except Exception as e:
                        logger.error(f"Worker restart failed: {e}")
            else:
                healthy.append(worker.worker_id)

                # Check GPU utilization
                if worker.gpu_utilization > self.GPU_UTIL_HIGH:
                    logger.warning(
                        f"Worker {worker.worker_id} GPU utilization high: "
                        f"{worker.gpu_utilization:.1f}%"
                    )

        result = {
            "checked": len(workers),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "offline": offline,
            "restarted": restarted,
            "timestamp": now.isoformat(),
        }

        # Publish system health event if issues found
        if unhealthy or offline:
            total_workers = len(workers)
            if total_workers > 0 and (len(unhealthy) + len(offline)) > total_workers / 2:
                event_type = EventType.SYSTEM_OVERLOAD
            else:
                event_type = EventType.ERROR_WORKER_CRASH

            if self.event_bus:
                self.event_bus.publish(
                    SystemEvent(
                        event_type=event_type,
                        payload={
                            "healthy": len(healthy),
                            "unhealthy": len(unhealthy),
                            "offline": len(offline),
                            "restarted": len(restarted),
                        },
                    )
                )

        return result

    async def check_gpu_health(self) -> Dict[str, Any]:
        """Check GPU health across all devices.

        Returns:
            Dict with per-GPU health status
        """
        if not self.worker_pool:
            return {"error": "Worker pool not configured"}

        workers = await self.worker_pool.list_workers()
        gpu_stats: Dict[int, Dict[str, Any]] = {}

        for worker in workers:
            gpu = worker.gpu_device
            if gpu not in gpu_stats:
                gpu_stats[gpu] = {
                    "device": gpu,
                    "workers": [],
                    "avg_utilization": 0.0,
                    "max_temperature": 0.0,
                    "total_memory_used": 0,
                    "status": "healthy",
                }

            stats = gpu_stats[gpu]
            stats["workers"].append(worker.worker_id)
            stats["avg_utilization"] = max(
                stats["avg_utilization"], worker.gpu_utilization
            )
            stats["total_memory_used"] += worker.gpu_memory_used

            # Check thresholds
            if stats["avg_utilization"] > self.GPU_UTIL_HIGH:
                stats["status"] = "busy"

        return {"gpus": list(gpu_stats.values()), "gpu_count": len(gpu_stats)}

    async def check_system_capacity(self) -> Dict[str, Any]:
        """Check overall system capacity and trigger degradation if needed.

        Returns:
            Dict with capacity assessment
        """
        if not self.worker_pool:
            return {"error": "Worker pool not configured"}

        capacity = await self.worker_pool.get_capacity()
        utilization = capacity["utilization"]

        status = "healthy"
        if utilization >= self.OVERLOAD_SESSION_RATIO:
            status = "critical"
        elif utilization >= self.DEGRADATION_TRIGGER:
            status = "degraded"

        result = {
            "status": status,
            "utilization": utilization,
            "available_slots": capacity["available_slots"],
            "total_slots": capacity["total_slots"],
            "active_workers": capacity["total_workers"],
            "degradation_active": self._degradation_active,
            "degradation_mode": self._degradation_mode,
        }

        # Auto-degradation logic
        if utilization >= self.DEGRADATION_TRIGGER and not self._degradation_active:
            await self._enable_degradation("cache_only", utilization)
        elif utilization <= self.RECOVERY_THRESHOLD and self._degradation_active:
            await self._disable_degradation(utilization)

        return result

    # ---- Status & Metrics ----

    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status.

        Returns:
            Dict with full system status overview
        """
        now = datetime.utcnow()

        # Get all metrics
        capacity: Dict[str, Any] = {}
        gpu_health: Dict[str, Any] = {}
        try:
            capacity = await self.check_system_capacity() if self.worker_pool else {}
            gpu_health = await self.check_gpu_health()
        except Exception as e:
            logger.error(f"Error checking system capacity: {e}")

        # Get call counts
        active_calls = 0
        queued_calls = 0
        if self.session_mgr:
            try:
                active_calls = await self.session_mgr.count_sessions(
                    state=CallState.ACTIVE.value
                )
                queued_calls = await self.session_mgr.count_sessions(
                    state=CallState.QUEUED.value
                )
            except Exception as e:
                logger.error(f"Error getting call counts: {e}")

        # Get today's total from Redis
        client = self._get_client()
        total_today = await client.get("stats:sessions:total_today") or "0"

        # Determine overall status
        overall = "healthy"
        if capacity.get("status") == "critical":
            overall = "critical"
        elif capacity.get("status") == "degraded" or self._degradation_active:
            overall = "degraded"

        # Get worker summary
        worker_summary: Dict[str, Any] = {"total": 0, "available": 0}
        if self.worker_pool:
            try:
                workers = await self.worker_pool.list_workers()
                worker_summary = {
                    "total": len(workers),
                    "available": sum(1 for w in workers if w.is_available),
                    "unhealthy": sum(
                        1 for w in workers if w.status == WorkerStatus.UNHEALTHY
                    ),
                    "offline": sum(
                        1 for w in workers if w.status == WorkerStatus.OFFLINE
                    ),
                    "idle": sum(
                        1 for w in workers if w.status == WorkerStatus.IDLE
                    ),
                    "busy": sum(
                        1 for w in workers if w.status == WorkerStatus.BUSY
                    ),
                    "draining": sum(
                        1 for w in workers if w.status == WorkerStatus.DRAINING
                    ),
                }
            except Exception as e:
                logger.error(f"Error getting worker summary: {e}")

        return {
            "status": overall,
            "timestamp": now.isoformat(),
            "version": "1.0.0",
            "calls": {
                "active": active_calls,
                "queued": queued_calls,
                "total_today": int(total_today),
            },
            "workers": worker_summary,
            "gpu": gpu_health,
            "capacity": capacity,
            "degradation": {
                "active": self._degradation_active,
                "mode": self._degradation_mode,
                "since": (
                    self._degradation_since.isoformat()
                    if self._degradation_since
                    else None
                ),
            },
        }

    async def get_prometheus_metrics(self) -> str:
        """Generate Prometheus-compatible metrics text.

        Returns:
            Multi-line string in Prometheus exposition format
        """
        lines: List[str] = []
        prefix = self.METRIC_PREFIX

        # Call metrics
        if self.session_mgr:
            for state in CallState:
                try:
                    count = await self.session_mgr.count_sessions(state=state.value)
                    lines.append(f'{prefix}_calls{{state="{state.value}"}} {count}')
                except Exception:
                    lines.append(f'{prefix}_calls{{state="{state.value}"}} 0')

        # Worker metrics
        if self.worker_pool:
            try:
                workers = await self.worker_pool.list_workers()
                for status in WorkerStatus:
                    count = sum(1 for w in workers if w.status == status)
                    lines.append(
                        f'{prefix}_workers{{status="{status.value}"}} {count}'
                    )

                for worker in workers:
                    lines.append(
                        f'{prefix}_worker_gpu_utilization{{'
                        f'worker="{worker.worker_id}",'
                        f'gpu="{worker.gpu_device}"}} '
                        f"{worker.gpu_utilization}"
                    )
                    lines.append(
                        f'{prefix}_worker_sessions{{'
                        f'worker="{worker.worker_id}"}} '
                        f"{len(worker.current_sessions)}"
                    )
                    lines.append(
                        f'{prefix}_worker_latency_ms{{'
                        f'worker="{worker.worker_id}"}} '
                        f"{worker.avg_inference_latency_ms}"
                    )
            except Exception as e:
                logger.error(f"Error generating worker metrics: {e}")

        # Degradation
        deg_value = 1 if self._degradation_active else 0
        lines.append(f"{prefix}_degradation_active {deg_value}")

        # Queue
        if self.session_mgr:
            try:
                queued = await self.session_mgr.count_sessions(
                    state=CallState.QUEUED.value
                )
                lines.append(f"{prefix}_queued_calls {queued}")
            except Exception:
                lines.append(f"{prefix}_queued_calls 0")

        return "\n".join(lines) + "\n"

    async def get_aggregate_stats(self) -> Dict[str, Any]:
        """Get aggregate worker statistics.

        Returns:
            Dict with aggregate statistics
        """
        if not self.worker_pool:
            return {"error": "Worker pool not configured"}

        workers = await self.worker_pool.list_workers()

        if not workers:
            return {"workers": 0}

        total_sessions = sum(len(w.current_sessions) for w in workers)
        avg_latency = (
            sum(w.avg_inference_latency_ms for w in workers) / len(workers)
            if workers
            else 0
        )
        total_requests = sum(w.total_requests_served for w in workers)
        total_errors = sum(w.errors_count for w in workers)

        return {
            "workers": len(workers),
            "total_sessions_active": total_sessions,
            "avg_inference_latency_ms": round(avg_latency, 2),
            "total_requests_served": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "avg_gpu_utilization": (
                sum(w.gpu_utilization for w in workers) / len(workers)
                if workers
                else 0
            ),
            "uptime_seconds_avg": (
                sum(
                    (datetime.utcnow() - w.started_at).total_seconds()
                    for w in workers
                )
                / len(workers)
                if workers
                else 0
            ),
        }

    # ---- Degradation Management ----

    async def _enable_degradation(self, mode: str, utilization: float) -> None:
        """Enable graceful degradation mode.

        Args:
            mode: Degradation mode (cache_only, reduced_quality, queue_only)
            utilization: Current system utilization
        """
        self._degradation_active = True
        self._degradation_mode = mode
        self._degradation_since = datetime.utcnow()

        client = self._get_client()
        await client.set("system:degradation:mode", mode)
        await client.set(
            "system:degradation:since", datetime.utcnow().isoformat()
        )

        logger.warning(f"Degradation enabled: mode={mode}, utilization={utilization:.0%}")

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.DEGRADATION_ENABLED,
                    payload={"mode": mode, "utilization": utilization},
                )
            )

    async def _disable_degradation(self, utilization: float) -> None:
        """Disable graceful degradation mode.

        Args:
            utilization: Current system utilization
        """
        self._degradation_active = False
        self._degradation_mode = "none"
        self._degradation_since = None

        client = self._get_client()
        await client.delete("system:degradation:mode")
        await client.delete("system:degradation:since")

        logger.info(f"Degradation disabled: utilization={utilization:.0%}")

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.DEGRADATION_DISABLED,
                    payload={"utilization": utilization},
                )
            )

    # ---- Worker State Changes ----

    async def _mark_unhealthy(self, worker: WorkerNode) -> None:
        """Mark a worker as unhealthy.

        Args:
            worker: WorkerNode to mark
        """
        client = self._get_client()
        key = f"worker:{worker.worker_id}"
        await client.hset(key, "status", WorkerStatus.UNHEALTHY.value)
        await client.hset(
            key, "status_changed_at", datetime.utcnow().isoformat()
        )

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.WORKER_UNHEALTHY,
                    worker_id=worker.worker_id,
                    payload={
                        "last_heartbeat": worker.last_heartbeat_at.isoformat()
                    },
                )
            )

        logger.warning(f"Worker {worker.worker_id} marked UNHEALTHY")

    async def _mark_offline(self, worker: WorkerNode) -> None:
        """Mark a worker as offline.

        Args:
            worker: WorkerNode to mark
        """
        client = self._get_client()
        key = f"worker:{worker.worker_id}"
        await client.hset(key, "status", WorkerStatus.OFFLINE.value)
        await client.hset(
            key, "status_changed_at", datetime.utcnow().isoformat()
        )

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.WORKER_OFFLINE,
                    worker_id=worker.worker_id,
                    payload={"current_sessions": worker.current_sessions},
                )
            )

        logger.error(f"Worker {worker.worker_id} marked OFFLINE")

    # ---- Restart Rate Limiting ----

    async def _can_restart(self, worker_id: str) -> bool:
        """Check if a worker can be restarted (rate limiting).

        Args:
            worker_id: Worker identifier

        Returns:
            True if restart is allowed
        """
        if not self.AUTO_RESTART_ENABLED:
            return False

        history = self._restart_history.get(worker_id, [])
        now = datetime.utcnow()

        # Filter to last hour
        recent = [t for t in history if (now - t).total_seconds() < 3600]
        self._restart_history[worker_id] = recent

        # Check cooldown
        if recent:
            last_restart = recent[-1]
            if (now - last_restart).total_seconds() < self.RESTART_COOLDOWN:
                return False

        # Check max attempts
        return len(recent) < self.MAX_RESTART_ATTEMPTS

    def _record_restart(self, worker_id: str) -> None:
        """Record a restart attempt for rate limiting.

        Args:
            worker_id: Worker identifier
        """
        if worker_id not in self._restart_history:
            self._restart_history[worker_id] = []
        self._restart_history[worker_id].append(datetime.utcnow())

    # ---- Alerting ----

    async def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for conditions that should trigger alerts.

        Returns:
            List of alert dictionaries
        """
        alerts: List[Dict[str, Any]] = []

        # Check worker health
        worker_check = await self.check_all_workers()
        if worker_check.get("unhealthy"):
            alerts.append(
                {
                    "level": "warning",
                    "type": "unhealthy_workers",
                    "message": f"{len(worker_check['unhealthy'])} workers unhealthy",
                    "workers": worker_check["unhealthy"],
                }
            )
        if worker_check.get("offline"):
            alerts.append(
                {
                    "level": "critical",
                    "type": "offline_workers",
                    "message": f"{len(worker_check['offline'])} workers offline",
                    "workers": worker_check["offline"],
                }
            )

        # Check capacity
        capacity = await self.check_system_capacity()
        if capacity.get("status") == "critical":
            alerts.append(
                {
                    "level": "critical",
                    "type": "capacity_critical",
                    "message": f"System capacity critical: {capacity.get('utilization', 0):.0%}",
                    "utilization": capacity.get("utilization"),
                }
            )
        elif capacity.get("status") == "degraded":
            alerts.append(
                {
                    "level": "warning",
                    "type": "capacity_degraded",
                    "message": f"System capacity degraded: {capacity.get('utilization', 0):.0%}",
                    "utilization": capacity.get("utilization"),
                }
            )

        # Check GPU health
        gpu_health = await self.check_gpu_health()
        for gpu in gpu_health.get("gpus", []):
            if gpu.get("status") in ("critical", "busy"):
                alerts.append(
                    {
                        "level": "warning",
                        "type": "gpu_high_utilization",
                        "message": f"GPU {gpu.get('device')} utilization high",
                        "gpu": gpu.get("device"),
                        "utilization": gpu.get("avg_utilization"),
                    }
                )

        return alerts

    # ---- GPU Metrics Recording ----

    async def record_gpu_metrics(
        self, device: int, utilization: float, memory_used: int, temperature: float
    ) -> None:
        """Record GPU metrics to Redis.

        Args:
            device: GPU device ID
            utilization: GPU utilization percentage
            memory_used: GPU memory used in MB
            temperature: GPU temperature in Celsius
        """
        client = self._get_client()
        await client.set(
            f"metrics:gpu:{device}:utilization", str(utilization)
        )
        await client.set(
            f"metrics:gpu:{device}:memory_used", str(memory_used)
        )
        await client.set(
            f"metrics:gpu:{device}:temperature", str(temperature)
        )

        # Check critical thresholds
        if temperature >= self.GPU_TEMP_CRITICAL:
            logger.critical(f"GPU {device} temperature critical: {temperature}C")
            if self.event_bus:
                self.event_bus.publish(
                    SystemEvent(
                        event_type=EventType.ERROR_GPU_OOM,
                        payload={
                            "gpu_device": device,
                            "temperature": temperature,
                            "utilization": utilization,
                        },
                    )
                )
