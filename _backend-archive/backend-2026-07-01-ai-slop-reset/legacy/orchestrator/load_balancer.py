"""
load_balancer.py -- GPU-aware load balancer for worker selection.

Strategies:
1. ROUND_ROBIN: Distribute evenly across workers
2. LEAST_LOAD: Assign to worker with most available slots (default)
3. GPU_AFFINITY: Prefer specific GPU for tenant/model
4. LATENCY_BASED: Route to worker with lowest avg latency

Default: LEAST_LOAD with GPU awareness.

Responsibilities:
- Select best worker for new calls
- Release workers after call ends
- Track worker capabilities and load
- GPU-aware task assignment
- Strategy selection and configuration

Integration Points:
- IN: Gateway (new call assignment)
- IN: SessionManager (session-worker mapping)
- OUT: WorkerPool (worker status queries)
- OUT: Redis (worker state)
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from legacy.orchestrator.models import WorkerNode, WorkerStatus

logger = logging.getLogger(__name__)


class LoadBalancer:
    """GPU-aware load balancer for assigning calls to workers.

    Supports multiple selection strategies and tracks worker capabilities
    for intelligent task distribution.

    Redis key patterns:
    - ``lb:rr_index`` -> STRING (round-robin counter)
    - ``lb:tenant_gpu:{tenant_id}`` -> STRING (preferred GPU for tenant)
    """

    STRATEGIES: List[str] = ["round_robin", "least_load", "latency_based", "gpu_affinity"]

    # Redis keys
    KEY_RR_INDEX: str = "lb:rr_index"
    KEY_TENANT_GPU: str = "lb:tenant_gpu:{tenant_id}"

    def __init__(
        self,
        worker_pool: Any,
        redis_client: Optional[Any] = None,
        strategy: str = "least_load",
        redis_url: str = "redis://localhost:6379/0",
    ):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Use one of {self.STRATEGIES}")

        self.worker_pool = worker_pool
        self.redis_url = redis_url
        self._redis: Optional[Any] = redis_client
        self.strategy = strategy

    def _get_client(self) -> Any:
        """Get or create async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis

    # ---- Core Assignment ----

    async def assign_worker(
        self,
        call_id: str,
        tenant_id: str,
        agent_id: str,
        preferred_gpu: Optional[int] = None,
    ) -> Optional[str]:
        """Select best worker for a new call.

        Uses the configured strategy to select from available workers.

        Args:
            call_id: Call identifier
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            preferred_gpu: Optional preferred GPU device

        Returns:
            worker_id or None if no workers available
        """
        available = await self.worker_pool.get_available_workers()

        if not available:
            logger.warning(f"No available workers for call {call_id}")
            return None

        # Filter by preferred GPU
        if preferred_gpu is not None:
            gpu_workers = [w for w in available if w.gpu_device == preferred_gpu]
            if gpu_workers:
                available = gpu_workers
            else:
                logger.debug(
                    f"Preferred GPU {preferred_gpu} not available, using any"
                )

        # Check tenant GPU affinity
        if not preferred_gpu:
            tenant_gpu = await self._get_tenant_gpu_preference(tenant_id)
            if tenant_gpu is not None:
                gpu_workers = [w for w in available if w.gpu_device == tenant_gpu]
                if gpu_workers:
                    available = gpu_workers

        # Apply strategy
        if self.strategy == "round_robin":
            worker = await self._round_robin(available)
        elif self.strategy == "least_load":
            worker = self._least_load(available)
        elif self.strategy == "latency_based":
            worker = self._latency_based(available)
        elif self.strategy == "gpu_affinity":
            worker = self._gpu_affinity(available, tenant_id)
        else:
            worker = self._least_load(available)

        if worker:
            # Assign session to worker via worker pool
            success = await self.worker_pool.assign_session(worker.worker_id, call_id)
            if success:
                logger.info(
                    f"Assigned call {call_id} to worker {worker.worker_id} "
                    f"(GPU {worker.gpu_device}, strategy={self.strategy}, "
                    f"slots={worker.available_slots - 1}/{worker.max_concurrent_sessions})"
                )
                return worker.worker_id
            else:
                logger.warning(
                    f"Worker {worker.worker_id} assignment failed for call {call_id}"
                )

        return None

    async def release_worker(self, worker_id: str, call_id: str) -> bool:
        """Release a worker after call ends.

        Args:
            worker_id: Worker identifier
            call_id: Call identifier

        Returns:
            True if released successfully
        """
        result = await self.worker_pool.release_session(worker_id, call_id)
        if result:
            logger.debug(f"Released worker {worker_id} from call {call_id}")
        return result

    # ---- Strategy Implementations ----

    async def _round_robin(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select worker using round-robin.

        Uses Redis counter for distributed consistency.

        Args:
            workers: Available workers

        Returns:
            Selected worker or None
        """
        if not workers:
            return None

        client = self._get_client()
        idx = await client.incr(self.KEY_RR_INDEX)
        idx = (int(idx) - 1) % len(workers)
        return workers[idx]

    def _least_load(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select worker with most available slots.

        Args:
            workers: Available workers

        Returns:
            Selected worker or None
        """
        if not workers:
            return None
        # Sort by available slots descending, then by latency ascending
        sorted_workers = sorted(
            workers,
            key=lambda w: (-w.available_slots, w.avg_inference_latency_ms),
        )
        return sorted_workers[0]

    def _latency_based(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select worker with lowest average latency.

        Prefers workers with no load (0 latency), then lowest latency.

        Args:
            workers: Available workers

        Returns:
            Selected worker or None
        """
        if not workers:
            return None
        # Prefer workers with 0 latency (no load), then lowest latency
        return min(
            workers,
            key=lambda w: (
                w.avg_inference_latency_ms if w.avg_inference_latency_ms > 0 else -1,
                -w.available_slots,
            ),
        )

    def _gpu_affinity(self, workers: List[WorkerNode], tenant_id: str) -> Optional[WorkerNode]:
        """Select worker considering tenant-GPU affinity.

        Currently falls back to least_load with tenant preference tracking.

        Args:
            workers: Available workers
            tenant_id: Tenant identifier

        Returns:
            Selected worker or None
        """
        # For now, falls back to least_load
        # Future: track tenant-GPU preferences in Redis
        return self._least_load(workers)

    # ---- Tenant GPU Preference ----

    async def set_tenant_gpu_preference(
        self, tenant_id: str, gpu_device: int
    ) -> bool:
        """Set preferred GPU for a tenant.

        Args:
            tenant_id: Tenant identifier
            gpu_device: Preferred GPU device ID

        Returns:
            True if set
        """
        client = self._get_client()
        key = self.KEY_TENANT_GPU.format(tenant_id=tenant_id)
        await client.set(key, str(gpu_device))
        logger.info(f"Set GPU preference for tenant {tenant_id}: GPU {gpu_device}")
        return True

    async def _get_tenant_gpu_preference(self, tenant_id: str) -> Optional[int]:
        """Get preferred GPU for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            GPU device ID or None
        """
        client = self._get_client()
        key = self.KEY_TENANT_GPU.format(tenant_id=tenant_id)
        val = await client.get(key)
        if val:
            return int(val)
        return None

    # ---- Worker Capability Tracking ----

    async def get_worker_capabilities(self) -> Dict[str, Any]:
        """Get capabilities summary for all workers.

        Returns:
            Dict with worker capability information
        """
        workers = await self.worker_pool.list_workers()
        capabilities: Dict[str, Any] = {
            "workers": [],
            "gpus": {},
            "models": set(),
        }

        for w in workers:
            worker_info = {
                "worker_id": w.worker_id,
                "gpu_device": w.gpu_device,
                "gpu_name": w.gpu_name,
                "available_slots": w.available_slots,
                "max_sessions": w.max_concurrent_sessions,
                "supported_models": w.supported_models,
                "avg_latency_ms": w.avg_inference_latency_ms,
                "version": w.version,
            }
            capabilities["workers"].append(worker_info)
            capabilities["models"].update(w.supported_models)

            gpu = w.gpu_device
            if gpu not in capabilities["gpus"]:
                capabilities["gpus"][gpu] = {
                    "workers": 0,
                    "total_slots": 0,
                    "available_slots": 0,
                }
            capabilities["gpus"][gpu]["workers"] += 1
            capabilities["gpus"][gpu]["total_slots"] += w.max_concurrent_sessions
            capabilities["gpus"][gpu]["available_slots"] += w.available_slots

        capabilities["models"] = list(capabilities["models"])
        return capabilities

    # ---- Health & Status ----

    async def get_status(self) -> Dict[str, Any]:
        """Get load balancer status.

        Returns:
            Dict with strategy, worker counts, availability
        """
        workers = await self.worker_pool.list_workers()
        available = [w for w in workers if w.is_available]

        return {
            "strategy": self.strategy,
            "total_workers": len(workers),
            "available_workers": len(available),
            "total_slots": sum(w.max_concurrent_sessions for w in workers),
            "available_slots": sum(w.available_slots for w in workers),
            "workers_by_status": {
                "idle": sum(1 for w in workers if w.status == WorkerStatus.IDLE),
                "busy": sum(1 for w in workers if w.status == WorkerStatus.BUSY),
                "starting": sum(
                    1 for w in workers if w.status == WorkerStatus.STARTING
                ),
                "draining": sum(
                    1 for w in workers if w.status == WorkerStatus.DRAINING
                ),
                "unhealthy": sum(
                    1 for w in workers if w.status == WorkerStatus.UNHEALTHY
                ),
                "offline": sum(
                    1 for w in workers if w.status == WorkerStatus.OFFLINE
                ),
            },
        }

    async def set_strategy(self, strategy: str) -> bool:
        """Change the load balancing strategy.

        Args:
            strategy: New strategy name

        Returns:
            True if changed

        Raises:
            ValueError: If strategy is not recognized
        """
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Use one of {self.STRATEGIES}"
            )
        old_strategy = self.strategy
        self.strategy = strategy
        logger.info(f"Load balancer strategy changed: {old_strategy} -> {strategy}")
        return True

    # ---- Batch Operations ----

    async def assign_workers_batch(
        self, assignments: List[Dict[str, Any]]
    ) -> List[Optional[str]]:
        """Assign multiple workers in batch.

        Args:
            assignments: List of dicts with call_id, tenant_id, agent_id, preferred_gpu

        Returns:
            List of worker_ids (None if assignment failed)
        """
        results: List[Optional[str]] = []
        for assign in assignments:
            worker_id = await self.assign_worker(
                call_id=assign["call_id"],
                tenant_id=assign["tenant_id"],
                agent_id=assign.get("agent_id", ""),
                preferred_gpu=assign.get("preferred_gpu"),
            )
            results.append(worker_id)
        return results

    async def rebalance_workers(self) -> Dict[str, Any]:
        """Rebalance load across workers.

        Identifies overloaded and underloaded workers and suggests
        reassignments.

        Returns:
            Dict with rebalance recommendations
        """
        workers = await self.worker_pool.list_workers()
        available = [w for w in workers if w.is_available]

        if len(available) < 2:
            return {"rebalanced": False, "reason": "not_enough_workers"}

        # Find most and least loaded workers
        by_load = sorted(available, key=lambda w: w.available_slots)
        most_loaded = by_load[0]
        least_loaded = by_load[-1]

        load_diff = least_loaded.available_slots - most_loaded.available_slots

        if load_diff <= 1:
            return {"rebalanced": False, "reason": "already_balanced"}

        return {
            "rebalanced": False,  # Actual reassignment requires session manager
            "recommendation": {
                "move_from": most_loaded.worker_id,
                "move_to": least_loaded.worker_id,
                "load_diff": load_diff,
                "sessions_to_move": min(
                    load_diff // 2,
                    len(most_loaded.current_sessions),
                ),
            },
        }
