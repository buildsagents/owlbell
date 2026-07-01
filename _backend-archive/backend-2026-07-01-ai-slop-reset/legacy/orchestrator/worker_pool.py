"""
worker_pool.py -- AI worker pool management with Celery integration.

Responsibilities:
- Register/unregister worker nodes
- Track worker capacity and assignments
- Dispatch AI tasks to Celery workers
- Auto-scale worker containers based on demand
- Handle worker lifecycle (start, drain, restart, stop)
- Rolling deployment support (version-aware)
- GPU-aware scheduling

Architecture:
- Workers are Celery workers running in Docker containers
- Each worker container has access to one GPU (via NVIDIA Docker runtime)
- Worker state is stored in Redis (heartbeat-based)
- Task routing uses Celery queues (ai, default)
- Auto-scaling uses Docker Compose scale command or container orchestrator

Celery Tasks:
- process_audio_chunk(call_id, audio_data) -> STT transcription
- generate_response(call_id, transcript) -> LLM response
- synthesize_speech(call_id, text) -> TTS audio
- handle_call_end(call_id) -> cleanup
- send_call_summary(call_id) -> post-call summary
- sync_calendar_events(tenant_id) -> periodic calendar sync

Integration Points:
- IN: Gateway (task dispatch)
- IN: HealthMonitor (restart decisions)
- IN: LoadBalancer (worker selection)
- OUT: Celery (task queue)
- OUT: Docker API (container management)
- OUT: Redis (worker state)
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from legacy.orchestrator.models import EventType, SystemEvent, WorkerNode, WorkerStatus

logger = logging.getLogger(__name__)


class WorkerPool:
    """Manages the pool of AI worker nodes.

    Provides worker registration, health tracking, task dispatch,
    auto-scaling, and lifecycle management.

    Redis key patterns:
    - ``worker:{worker_id}`` -> HASH (worker data)
    - ``workers:all`` -> SET (all worker IDs)
    - ``workers:status:{status}`` -> SET (worker IDs by status)
    - ``gpu:{gpu_device}:workers`` -> SET (workers on GPU)
    """

    # Redis key prefixes
    KEY_WORKER: str = "worker"
    KEY_WORKERS_ALL: str = "workers:all"
    KEY_WORKERS_STATUS: str = "workers:status"
    KEY_GPU_WORKERS: str = "gpu:{gpu}:workers"

    # Worker heartbeat TTL in seconds
    HEARTBEAT_TTL: int = 10

    # Auto-scale settings
    SCALE_UP_THRESHOLD: float = 0.85
    SCALE_DOWN_THRESHOLD: float = 0.30
    MIN_WORKERS: int = 1
    MAX_WORKERS: int = 8

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        celery_app: Optional[Any] = None,
        redis_url: str = "redis://localhost:6379/0",
        docker_compose_file: str = "/app/docker-compose.yml",
    ):
        self.redis_url = redis_url
        self._redis: Optional[Any] = redis_client
        self.event_bus = event_bus
        self.celery = celery_app
        self.docker_compose_file = docker_compose_file

    def _get_client(self) -> Any:
        """Get or create async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis

    # ---- Worker Registration ----

    async def register_worker(self, worker: WorkerNode) -> WorkerNode:
        """Register a new worker in the pool.

        Called when worker starts up and sends initial heartbeat.

        Args:
            worker: WorkerNode with capabilities and status

        Returns:
            Registered worker (may have max_concurrent_sessions adjusted)
        """
        client = self._get_client()
        key = self._worker_key(worker.worker_id)

        # Calculate max sessions based on GPU VRAM
        # Rough heuristic: 4 sessions per 8GB VRAM
        vram_gb = worker.gpu_memory_total / 1024
        worker.max_concurrent_sessions = max(1, min(8, int(vram_gb / 2)))

        # Store worker hash
        await client.hset(key, mapping=worker.to_redis_hash())
        await client.expire(key, self.HEARTBEAT_TTL * 2)

        # Add to indexes
        pipe = client.pipeline()
        pipe.sadd(self.KEY_WORKERS_ALL, worker.worker_id)
        pipe.sadd(
            f"{self.KEY_WORKERS_STATUS}:{worker.status.value}", worker.worker_id
        )
        pipe.sadd(
            self.KEY_GPU_WORKERS.format(gpu=worker.gpu_device), worker.worker_id
        )
        await pipe.execute()

        logger.info(
            f"Worker registered: {worker.worker_id} on GPU {worker.gpu_device} "
            f"(max {worker.max_concurrent_sessions} sessions, "
            f"GPU={worker.gpu_name})"
        )

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.WORKER_STARTED,
                    worker_id=worker.worker_id,
                    payload={
                        "gpu_device": worker.gpu_device,
                        "gpu_name": worker.gpu_name,
                        "max_sessions": worker.max_concurrent_sessions,
                        "version": worker.version,
                        "hostname": worker.hostname,
                    },
                )
            )

        return worker

    async def unregister_worker(self, worker_id: str, reason: str = "shutdown") -> bool:
        """Unregister a worker from the pool.

        Args:
            worker_id: Worker identifier
            reason: Reason for unregistration

        Returns:
            True if worker was registered
        """
        client = self._get_client()
        worker = await self.get_worker(worker_id)
        if not worker:
            return False

        key = self._worker_key(worker_id)

        # Remove from indexes
        pipe = client.pipeline()
        pipe.srem(self.KEY_WORKERS_ALL, worker_id)
        for status in WorkerStatus:
            pipe.srem(f"{self.KEY_WORKERS_STATUS}:{status.value}", worker_id)
        if worker.gpu_device is not None:
            pipe.srem(
                self.KEY_GPU_WORKERS.format(gpu=worker.gpu_device), worker_id
            )
        pipe.delete(key)
        await pipe.execute()

        logger.info(f"Worker unregistered: {worker_id} (reason: {reason})")
        return True

    async def heartbeat(self, worker_id: str, metrics: Dict[str, Any]) -> bool:
        """Process worker heartbeat.

        Updates worker metrics and refreshes TTL.

        Args:
            worker_id: Worker identifier
            metrics: Dict with cpu_percent, memory_percent, gpu_utilization, etc.

        Returns:
            True if heartbeat accepted
        """
        client = self._get_client()
        key = self._worker_key(worker_id)

        # Check if worker exists
        exists = await client.exists(key)
        if not exists:
            logger.warning(f"Heartbeat from unknown worker: {worker_id}")
            return False

        # Update metrics
        updates = {
            "cpu_percent": str(metrics.get("cpu_percent", 0)),
            "memory_percent": str(metrics.get("memory_percent", 0)),
            "gpu_utilization": str(metrics.get("gpu_utilization", 0)),
            "gpu_memory_used": str(metrics.get("gpu_memory_used", 0)),
            "gpu_memory_free": str(metrics.get("gpu_memory_free", 0)),
            "gpu_temperature": str(metrics.get("gpu_temperature", 0)),
            "avg_inference_latency_ms": str(
                metrics.get("avg_inference_latency_ms", 0)
            ),
            "total_requests_served": str(
                metrics.get("total_requests_served", 0)
            ),
            "errors_count": str(metrics.get("errors_count", 0)),
            "last_heartbeat_at": datetime.utcnow().isoformat(),
            "current_sessions": json.dumps(
                metrics.get("current_sessions", [])
            ),
        }

        # Update status if changed
        new_status = metrics.get("status")
        if new_status:
            old_status = await client.hget(key, "status")
            if old_status != new_status:
                updates["status"] = new_status
                updates["status_changed_at"] = datetime.utcnow().isoformat()
                # Update status indexes
                pipe = client.pipeline()
                pipe.srem(
                    f"{self.KEY_WORKERS_STATUS}:{old_status}", worker_id
                )
                pipe.sadd(
                    f"{self.KEY_WORKERS_STATUS}:{new_status}", worker_id
                )
                await pipe.execute()

                if self.event_bus:
                    event_map = {
                        "idle": EventType.WORKER_IDLE,
                        "busy": EventType.WORKER_BUSY,
                        "draining": EventType.WORKER_DRAINING,
                        "unhealthy": EventType.WORKER_UNHEALTHY,
                        "offline": EventType.WORKER_OFFLINE,
                    }
                    event_type = event_map.get(new_status)
                    if event_type:
                        self.event_bus.publish(
                            SystemEvent(
                                event_type=event_type,
                                worker_id=worker_id,
                                payload={"old_status": old_status},
                            )
                        )

        pipe = client.pipeline()
        pipe.hset(key, mapping=updates)
        pipe.expire(key, self.HEARTBEAT_TTL * 2)
        await pipe.execute()

        return True

    # ---- Queries ----

    async def get_worker(self, worker_id: str) -> Optional[WorkerNode]:
        """Get worker by ID.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerNode or None
        """
        client = self._get_client()
        key = self._worker_key(worker_id)
        data = await client.hgetall(key)
        if not data:
            return None
        return WorkerNode.from_redis_hash(data)

    async def list_workers(
        self, status: Optional[WorkerStatus] = None
    ) -> List[WorkerNode]:
        """List workers, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of WorkerNode objects
        """
        client = self._get_client()
        if status:
            worker_ids = await client.smembers(
                f"{self.KEY_WORKERS_STATUS}:{status.value}"
            )
        else:
            worker_ids = await client.smembers(self.KEY_WORKERS_ALL)

        workers: List[WorkerNode] = []
        for wid in sorted(worker_ids):
            worker = await self.get_worker(wid)
            if worker:
                workers.append(worker)
        return workers

    async def get_available_workers(self) -> List[WorkerNode]:
        """Get workers that can accept new sessions.

        Returns:
            List of available WorkerNode objects
        """
        all_workers = await self.list_workers()
        return [w for w in all_workers if w.is_available]

    async def get_capacity(self) -> Dict[str, Any]:
        """Get current pool capacity.

        Returns:
            Dict with capacity information
        """
        workers = await self.list_workers()
        total_slots = sum(w.max_concurrent_sessions for w in workers)
        used_slots = sum(len(w.current_sessions) for w in workers)

        return {
            "total_workers": len(workers),
            "total_slots": total_slots,
            "used_slots": used_slots,
            "available_slots": total_slots - used_slots,
            "utilization": used_slots / total_slots if total_slots > 0 else 0,
            "by_gpu": self._group_by_gpu(workers),
        }

    # ---- Assignment Management ----

    async def assign_session(self, worker_id: str, call_id: str) -> bool:
        """Assign a call session to a worker.

        Updates worker's current_sessions and status.

        Args:
            worker_id: Worker identifier
            call_id: Call identifier

        Returns:
            True if assignment successful
        """
        client = self._get_client()
        worker = await self.get_worker(worker_id)
        if not worker:
            return False

        if not worker.is_available:
            return False

        # Add call to worker's sessions
        sessions = list(worker.current_sessions)
        if call_id in sessions:
            return True  # Already assigned

        sessions.append(call_id)

        # Update status
        new_status = (
            WorkerStatus.BUSY
            if len(sessions) >= worker.max_concurrent_sessions
            else WorkerStatus.IDLE
        )

        key = self._worker_key(worker_id)
        pipe = client.pipeline()
        pipe.hset(key, "current_sessions", json.dumps(sessions))

        # Update status index if changed
        if new_status != worker.status:
            pipe.hset(key, "status", new_status.value)
            pipe.srem(
                f"{self.KEY_WORKERS_STATUS}:{worker.status.value}", worker_id
            )
            pipe.sadd(
                f"{self.KEY_WORKERS_STATUS}:{new_status.value}", worker_id
            )

        await pipe.execute()
        return True

    async def release_session(self, worker_id: str, call_id: str) -> bool:
        """Release a call session from a worker.

        Called when call ends or is transferred.

        Args:
            worker_id: Worker identifier
            call_id: Call identifier

        Returns:
            True if release successful
        """
        client = self._get_client()
        worker = await self.get_worker(worker_id)
        if not worker:
            return False

        sessions = list(worker.current_sessions)
        if call_id not in sessions:
            return True  # Already released

        sessions.remove(call_id)

        # Determine new status
        if worker.status == WorkerStatus.DRAINING and len(sessions) == 0:
            new_status = WorkerStatus.DRAINING  # Keep draining
        elif len(sessions) == 0:
            new_status = WorkerStatus.IDLE
        else:
            new_status = WorkerStatus.BUSY  # Still has sessions

        key = self._worker_key(worker_id)
        pipe = client.pipeline()
        pipe.hset(key, "current_sessions", json.dumps(sessions))

        if new_status != worker.status:
            pipe.hset(key, "status", new_status.value)
            pipe.srem(
                f"{self.KEY_WORKERS_STATUS}:{worker.status.value}", worker_id
            )
            pipe.sadd(
                f"{self.KEY_WORKERS_STATUS}:{new_status.value}", worker_id
            )

        await pipe.execute()

        logger.debug(f"Released call {call_id} from worker {worker_id}")
        return True

    # ---- Task Dispatch ----

    def dispatch_stt_llm_tts(
        self, call_id: str, audio_b64: str
    ) -> Any:
        """Dispatch full AI pipeline task to Celery.

        Args:
            call_id: Session identifier
            audio_b64: Base64-encoded caller audio

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            logger.error("Celery app not configured")
            return None

        result = self.celery.send_task(
            "orchestrator.tasks.ai_pipeline",
            args=[call_id, audio_b64],
            queue="ai",
            priority=0,
            time_limit=45,
            soft_time_limit=25,
        )

        logger.debug(
            f"Dispatched pipeline task for call {call_id}, "
            f"task_id={result.id if result else 'none'}"
        )
        return result

    def dispatch_stt(self, call_id: str, audio_b64: str) -> Any:
        """Dispatch STT-only task.

        Args:
            call_id: Session identifier
            audio_b64: Base64-encoded audio data

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None

        return self.celery.send_task(
            "orchestrator.tasks.ai_stt",
            args=[call_id, audio_b64],
            queue="ai",
        )

    def dispatch_llm(
        self, call_id: str, transcript: list, agent_config: dict
    ) -> Any:
        """Dispatch LLM-only task.

        Args:
            call_id: Session identifier
            transcript: Conversation transcript
            agent_config: Agent configuration

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None

        return self.celery.send_task(
            "orchestrator.tasks.ai_llm",
            args=[call_id, transcript, agent_config],
            queue="ai",
        )

    def dispatch_tts(
        self, call_id: str, text: str, voice_id: Optional[str] = None
    ) -> Any:
        """Dispatch TTS-only task.

        Args:
            call_id: Session identifier
            text: Text to synthesize
            voice_id: Optional voice identifier

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None

        return self.celery.send_task(
            "orchestrator.tasks.ai_tts",
            args=[call_id, text],
            kwargs={"voice_id": voice_id},
            queue="ai",
        )

    def process_audio_chunk(self, call_id: str, audio_data: str) -> Any:
        """Process audio chunk: STT -> LLM -> TTS pipeline.

        Args:
            call_id: Session identifier
            audio_data: Base64-encoded PCM audio

        Returns:
            Celery AsyncResult
        """
        return self.dispatch_stt_llm_tts(call_id, audio_data)

    def generate_response(self, call_id: str, transcript: list) -> Any:
        """Generate AI response from transcript.

        Args:
            call_id: Session identifier
            transcript: Conversation transcript

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None
        return self.celery.send_task(
            "orchestrator.tasks.ai_llm",
            args=[call_id, transcript, {}],
            queue="ai",
        )

    def synthesize_speech(self, call_id: str, text: str) -> Any:
        """Synthesize speech from text.

        Args:
            call_id: Session identifier
            text: Text to synthesize

        Returns:
            Celery AsyncResult
        """
        return self.dispatch_tts(call_id, text)

    def handle_call_end(self, call_id: str) -> Any:
        """Handle call end cleanup.

        Args:
            call_id: Session identifier

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None
        return self.celery.send_task(
            "orchestrator.tasks.archive_session",
            args=[call_id],
            queue="default",
        )

    def send_call_summary(self, call_id: str) -> Any:
        """Send call summary notification.

        Args:
            call_id: Session identifier

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None
        return self.celery.send_task(
            "orchestrator.tasks.send_call_summary",
            args=[call_id],
            queue="default",
        )

    def sync_calendar_events(self, tenant_id: str) -> Any:
        """Sync calendar events for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Celery AsyncResult
        """
        if self.celery is None:
            return None
        return self.celery.send_task(
            "orchestrator.tasks.sync_calendar_events",
            args=[tenant_id],
            queue="default",
        )

    # ---- Lifecycle Management ----

    async def drain_worker(self, worker_id: str) -> bool:
        """Drain worker: finish current calls, no new assignments.

        Used for graceful shutdown and rolling deployments.

        Args:
            worker_id: Worker identifier

        Returns:
            True if draining initiated
        """
        client = self._get_client()
        worker = await self.get_worker(worker_id)
        if not worker:
            return False

        key = self._worker_key(worker_id)

        # Update status
        pipe = client.pipeline()
        pipe.hset(key, "status", WorkerStatus.DRAINING.value)
        pipe.hset(key, "status_changed_at", datetime.utcnow().isoformat())
        pipe.srem(
            f"{self.KEY_WORKERS_STATUS}:{worker.status.value}", worker_id
        )
        pipe.sadd(
            f"{self.KEY_WORKERS_STATUS}:{WorkerStatus.DRAINING.value}", worker_id
        )
        await pipe.execute()

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.WORKER_DRAINING,
                    worker_id=worker_id,
                    payload={"current_sessions": len(worker.current_sessions)},
                )
            )

        logger.info(
            f"Worker {worker_id} draining "
            f"({len(worker.current_sessions)} active sessions)"
        )
        return True

    async def restart_worker(self, worker_id: str) -> Dict[str, Any]:
        """Restart a worker container.

        1. Drain worker (no new assignments)
        2. Wait for current sessions to finish (or timeout)
        3. Kill container via Docker
        4. Docker Compose will restart it

        Args:
            worker_id: Worker identifier

        Returns:
            Dict with restart status
        """
        worker = await self.get_worker(worker_id)
        if not worker:
            return {"error": "Worker not found", "worker_id": worker_id}

        # Drain first
        await self.drain_worker(worker_id)

        # Wait for sessions to finish (up to 60 seconds)
        for i in range(60):
            worker = await self.get_worker(worker_id)
            if not worker or len(worker.current_sessions) == 0:
                break
            await asyncio.sleep(1)

        # Force kill container
        try:
            container_name = worker.hostname
            subprocess.run(
                ["docker", "kill", "--signal=SIGTERM", container_name],
                check=True,
                capture_output=True,
                timeout=10,
            )

            logger.info(f"Worker container killed: {container_name}")

            if self.event_bus:
                self.event_bus.publish(
                    SystemEvent(
                        event_type=EventType.WORKER_RESTARTED,
                        worker_id=worker_id,
                        payload={"hostname": container_name},
                    )
                )

            return {
                "status": "restarting",
                "worker_id": worker_id,
                "container": container_name,
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to kill worker container: {e}")
            return {"error": str(e), "worker_id": worker_id}
        except subprocess.TimeoutExpired:
            logger.error("Timeout killing worker container")
            return {"error": "timeout", "worker_id": worker_id}

    async def scale_workers(self, target_count: int) -> Dict[str, Any]:
        """Scale worker containers using Docker Compose.

        Args:
            target_count: Desired number of worker containers

        Returns:
            Dict with scale operation result
        """
        try:
            result = subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    self.docker_compose_file,
                    "up",
                    "-d",
                    "--scale",
                    f"worker={target_count}",
                    "--no-recreate",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

            logger.info(f"Scaled workers to {target_count}")
            return {
                "status": "scaled",
                "target": target_count,
                "output": result.stdout,
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Scale failed: {e}")
            return {"error": str(e), "stderr": e.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "Scale command timed out"}

    # ---- Auto-scaling ----

    async def auto_scale(self) -> Optional[Dict[str, Any]]:
        """Evaluate current load and auto-scale if needed.

        Called periodically by Celery beat task.

        Returns:
            Scale action dict or None if no action needed
        """
        capacity = await self.get_capacity()
        utilization = capacity["utilization"]
        current_workers = capacity["total_workers"]

        if utilization >= self.SCALE_UP_THRESHOLD:
            target = min(current_workers + 1, self.MAX_WORKERS)
            if target > current_workers:
                logger.info(
                    f"Auto-scaling up: {current_workers} -> {target} "
                    f"(utilization: {utilization:.0%})"
                )
                return await self.scale_workers(target)

        elif utilization <= self.SCALE_DOWN_THRESHOLD:
            target = max(current_workers - 1, self.MIN_WORKERS)
            if target < current_workers:
                # Only scale down idle workers
                idle_workers = await self.list_workers(WorkerStatus.IDLE)
                if len(idle_workers) > 0:
                    # Drain one idle worker
                    await self.drain_worker(idle_workers[0].worker_id)
                    logger.info(
                        f"Auto-scaling down: draining {idle_workers[0].worker_id} "
                        f"(utilization: {utilization:.0%})"
                    )
                    return {
                        "status": "draining",
                        "worker_id": idle_workers[0].worker_id,
                    }

        return None

    # ---- Rolling Deployment ----

    async def start_rolling_deployment(self, new_version: str) -> Dict[str, Any]:
        """Start a rolling deployment to new version.

        Strategy:
        1. Start new worker containers with new version
        2. Mark old workers as DRAINING
        3. Wait for old workers to finish current sessions
        4. Remove old worker containers

        Args:
            new_version: Target version string

        Returns:
            Deployment status dict
        """
        current_workers = await self.list_workers()
        old_workers = [w for w in current_workers if w.version != new_version]

        if not old_workers:
            return {
                "status": "no_change",
                "message": "All workers already at target version",
            }

        # Start new workers first
        target_count = len(current_workers)

        client = self._get_client()
        # Set deployment in progress flag
        await client.set("deployment:in_progress", new_version)
        await client.set(
            "deployment:started_at", datetime.utcnow().isoformat()
        )

        # Drain old workers
        for worker in old_workers:
            await self.drain_worker(worker.worker_id)

        return {
            "status": "rolling",
            "new_version": new_version,
            "workers_to_replace": len(old_workers),
            "target_total": target_count,
        }

    async def check_deployment_complete(self) -> Dict[str, Any]:
        """Check if rolling deployment is complete.

        Returns:
            Deployment status dict
        """
        client = self._get_client()
        in_progress = await client.get("deployment:in_progress")
        if not in_progress:
            return {"status": "none"}

        # Count old-version workers still active
        current_workers = await self.list_workers()
        old_workers = [w for w in current_workers if w.version != in_progress]

        if not old_workers:
            await client.delete("deployment:in_progress")
            await client.delete("deployment:started_at")
            return {"status": "complete", "version": in_progress}

        return {
            "status": "in_progress",
            "version": in_progress,
            "remaining_old_workers": len(old_workers),
            "old_workers": [w.worker_id for w in old_workers],
        }

    # ---- Utility ----

    def _worker_key(self, worker_id: str) -> str:
        """Build Redis key for worker hash.

        Args:
            worker_id: Worker identifier

        Returns:
            Redis key string
        """
        return f"{self.KEY_WORKER}:{worker_id}"

    def _group_by_gpu(self, workers: List[WorkerNode]) -> Dict[str, Any]:
        """Group workers by GPU device for capacity reporting.

        Args:
            workers: List of workers

        Returns:
            Dict grouped by GPU device
        """
        by_gpu: Dict[int, Dict[str, Any]] = {}
        for w in workers:
            gpu = w.gpu_device if w.gpu_device is not None else -1
            if gpu not in by_gpu:
                by_gpu[gpu] = {
                    "workers": 0,
                    "total_slots": 0,
                    "used_slots": 0,
                }
            by_gpu[gpu]["workers"] += 1
            by_gpu[gpu]["total_slots"] += w.max_concurrent_sessions
            by_gpu[gpu]["used_slots"] += len(w.current_sessions)

        for gpu, data in by_gpu.items():
            data["available_slots"] = data["total_slots"] - data["used_slots"]
            data["utilization"] = (
                data["used_slots"] / data["total_slots"]
                if data["total_slots"] > 0
                else 0
            )

        return {str(k): v for k, v in by_gpu.items()}
