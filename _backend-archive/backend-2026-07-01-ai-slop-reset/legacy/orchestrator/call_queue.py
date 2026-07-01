"""
call_queue.py -- Priority call queue with wait time estimation.

Uses Redis Sorted Sets for priority queue.
Score format: priority.unix_timestamp (lower = higher priority)
Supports per-tenant queues and global overflow queue.

Responsibilities:
- Enqueue calls with priority levels
- Dequeue highest priority calls
- Estimate wait times using EMA
- Queue position announcements
- Overflow handling
- Priority adjustments

Priority Levels:
- EMERGENCY (1): 911/urgent redirects
- VIP (10): Whitelist numbers
- CALLBACK (20): Return calls
- STANDARD (30): Normal calls
- LOW (40): Non-urgent/after-hours

Integration Points:
- IN: Gateway (incoming calls)
- IN: SessionManager (queue transitions)
- OUT: EventBus (queue events)
- OUT: LoadBalancer (worker assignment)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from legacy.orchestrator.models import CallState, EventType, QueuePriority, QueuedCall, SystemEvent

logger = logging.getLogger(__name__)


class CallQueue:
    """Priority call queue using Redis Sorted Sets.

    Redis key patterns:
    - ``queue:{tenant_id}`` -> Sorted Set (score: priority.timestamp, member: call_id)
    - ``queue:global`` -> Sorted Set (global overflow)
    - ``queued_call:{call_id}`` -> HASH (call details)
    - ``stats:queue:{tenant_id}:avg_wait`` -> STRING (EMA of wait times)
    """

    KEY_QUEUE: str = "queue:{tenant_id}"
    KEY_GLOBAL_QUEUE: str = "queue:global"
    KEY_QUEUED_CALL: str = "queued_call:{call_id}"
    KEY_STATS_AVG_WAIT: str = "stats:queue:{tenant_id}:avg_wait"
    KEY_STATS_TOTAL_WAITED: str = "stats:queue:{tenant_id}:total_waited"

    # Announcement settings
    ANNOUNCE_INTERVAL_SECONDS: int = 30
    ANNOUNCE_FIRST_AFTER: int = 10

    # EMA alpha for wait time estimation (0.3 = responsive but stable)
    EMA_ALPHA: float = 0.3

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        redis_url: str = "redis://localhost:6379/0",
    ):
        self.redis_url = redis_url
        self._redis: Optional[Any] = redis_client
        self.event_bus = event_bus
        self.session_mgr = session_manager

    def _get_client(self) -> Any:
        """Get or create async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis

    # ---- Core Queue Operations ----

    async def enqueue(
        self,
        call_id: str,
        tenant_id: str,
        caller_number: str,
        priority: QueuePriority = QueuePriority.STANDARD,
        caller_name: Optional[str] = None,
        requested_agent_id: Optional[str] = None,
        transfer_target: Optional[str] = None,
        queue_reason: str = "no_workers_available",
    ) -> int:
        """Add a call to the priority queue.

        Args:
            call_id: Call identifier
            tenant_id: Tenant identifier
            caller_number: Caller phone number
            priority: Queue priority level
            caller_name: Optional caller name
            requested_agent_id: Optional requested agent
            transfer_target: Optional transfer target
            queue_reason: Reason for queuing

        Returns:
            Queue position (1-based)
        """
        client = self._get_client()

        queued_call = QueuedCall(
            call_id=call_id,
            tenant_id=tenant_id,
            caller_number=caller_number,
            caller_name=caller_name,
            priority=priority,
            queue_entered_at=datetime.utcnow(),
            requested_agent_id=requested_agent_id,
            transfer_target=transfer_target,
            queue_reason=queue_reason,
        )

        # Store call details
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        await client.hset(call_key, mapping=queued_call.model_dump(mode="json"))
        await client.expire(call_key, 3600)

        # Add to tenant queue
        queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
        score = queued_call.get_queue_score()
        await client.zadd(queue_key, {call_id: score})

        # Also add to global queue
        await client.zadd(self.KEY_GLOBAL_QUEUE, {call_id: score})

        # Get position
        position = await client.zrank(queue_key, call_id)
        position = (position or 0) + 1  # 1-based

        # Update position in hash
        await client.hset(call_key, "position", str(position))

        # Update session state if session manager available
        if self.session_mgr:
            try:
                await self.session_mgr.update_session(
                    call_id,
                    {
                        "state": CallState.QUEUED,
                        "queue_position": position,
                        "queue_entered_at": datetime.utcnow(),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to update session state for queued call: {e}")

        # Publish event
        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.CALL_QUEUED,
                    call_id=call_id,
                    tenant_id=tenant_id,
                    payload={
                        "position": position,
                        "priority": priority.value,
                        "queue_reason": queue_reason,
                        "caller_number": caller_number,
                    },
                )
            )

        logger.info(
            f"Call {call_id} queued at position {position} "
            f"(priority={priority.name}/{priority.value})"
        )

        return position

    async def dequeue(
        self, tenant_id: Optional[str] = None
    ) -> Optional[QueuedCall]:
        """Get highest priority call from queue.

        Checks tenant queue first, then global queue.

        Args:
            tenant_id: Optional tenant to prioritize

        Returns:
            QueuedCall or None if queue empty
        """
        client = self._get_client()
        call_id: Optional[str] = None

        if tenant_id:
            # Check tenant-specific queue first
            queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
            result = await client.zrange(queue_key, 0, 0)
            if result:
                call_id = result[0]

        if not call_id:
            # Check global queue
            result = await client.zrange(self.KEY_GLOBAL_QUEUE, 0, 0)
            if result:
                call_id = result[0]

        if not call_id:
            return None

        # Get call details
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        if not data:
            # Stale entry, remove and try again
            await self._remove_from_queues(call_id, tenant_id)
            return await self.dequeue(tenant_id)

        # Remove from queues
        actual_tenant = data.get("tenant_id", tenant_id)
        await self._remove_from_queues(call_id, actual_tenant)

        return QueuedCall.model_validate(data)

    async def peek(
        self, tenant_id: Optional[str] = None
    ) -> Optional[QueuedCall]:
        """Peek at highest priority call without removing.

        Args:
            tenant_id: Optional tenant filter

        Returns:
            QueuedCall or None
        """
        client = self._get_client()
        call_id: Optional[str] = None

        if tenant_id:
            queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
            result = await client.zrange(queue_key, 0, 0)
            if result:
                call_id = result[0]

        if not call_id:
            result = await client.zrange(self.KEY_GLOBAL_QUEUE, 0, 0)
            if result:
                call_id = result[0]

        if not call_id:
            return None

        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        if not data:
            return None

        return QueuedCall.model_validate(data)

    async def remove_call(self, call_id: str) -> bool:
        """Remove a call from all queues.

        Args:
            call_id: Call identifier

        Returns:
            True if removed
        """
        client = self._get_client()
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        tenant_id = data.get("tenant_id") if data else None

        await self._remove_from_queues(call_id, tenant_id)
        await client.delete(call_key)

        return True

    # ---- Queue Position & Wait Time ----

    async def get_position(self, call_id: str, tenant_id: str) -> int:
        """Get current queue position (1-based).

        Args:
            call_id: Call identifier
            tenant_id: Tenant identifier

        Returns:
            Queue position (0 if not in queue)
        """
        client = self._get_client()
        queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
        position = await client.zrank(queue_key, call_id)
        return (position or -1) + 1

    async def get_wait_estimate(self, tenant_id: str, position: int) -> int:
        """Estimate wait time in seconds for a given queue position.

        Uses exponential moving average of actual wait times.

        Args:
            tenant_id: Tenant identifier
            position: Queue position

        Returns:
            Estimated wait in seconds
        """
        client = self._get_client()

        # Get average wait time for tenant
        avg_wait_raw = await client.get(
            self.KEY_STATS_AVG_WAIT.format(tenant_id=tenant_id)
        )
        avg_wait = float(avg_wait_raw) if avg_wait_raw else 30.0

        # Get global average if tenant average not available
        if not avg_wait_raw:
            global_avg = await client.get(self.KEY_STATS_AVG_WAIT.format(tenant_id="global"))
            if global_avg:
                avg_wait = float(global_avg)

        # Estimate: avg_wait * position
        return int(avg_wait * max(1, position))

    async def should_announce(self, call_id: str) -> bool:
        """Check if a queue position announcement should be made.

        Args:
            call_id: Call identifier

        Returns:
            True if announcement is due
        """
        client = self._get_client()
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        if not data:
            return False

        last_announcement = data.get("last_announcement_at")
        announcements_count = int(data.get("announcements_count", 0))
        entered_at = data.get("queue_entered_at")

        if not entered_at:
            return False

        now = datetime.utcnow()
        entered = datetime.fromisoformat(entered_at)
        elapsed = (now - entered).total_seconds()

        # First announcement after ANNOUNCE_FIRST_AFTER seconds
        if announcements_count == 0:
            return elapsed >= self.ANNOUNCE_FIRST_AFTER

        # Subsequent announcements every ANNOUNCE_INTERVAL_SECONDS
        if last_announcement:
            last = datetime.fromisoformat(last_announcement)
            return (now - last).total_seconds() >= self.ANNOUNCE_INTERVAL_SECONDS

        return False

    async def record_announcement(self, call_id: str) -> None:
        """Record that an announcement was made.

        Args:
            call_id: Call identifier
        """
        client = self._get_client()
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        if not data:
            return

        count = int(data.get("announcements_count", 0)) + 1
        await client.hset(
            call_key,
            mapping={
                "last_announcement_at": datetime.utcnow().isoformat(),
                "announcements_count": str(count),
            },
        )

    # ---- Queue Status ----

    async def get_global_status(self) -> Dict[str, Any]:
        """Get global queue status.

        Returns:
            Dict with total queued, per-enant breakdown, capacity info
        """
        client = self._get_client()
        global_count = await client.zcard(self.KEY_GLOBAL_QUEUE)

        # Get per-tenant counts
        tenant_queue_keys = await client.keys(self.KEY_QUEUE.format(tenant_id="*"))
        by_tenant: Dict[str, Dict[str, Any]] = {}
        for tq in tenant_queue_keys:
            parts = tq.split(":")
            if len(parts) >= 2:
                tid = parts[-1]
                count = await client.zcard(tq)
                if count > 0:
                    # Get longest wait
                    oldest = await client.zrange(tq, 0, 0, withscores=True)
                    longest_wait = 0
                    if oldest:
                        score = oldest[0][1]
                        priority = int(score)
                        timestamp = score - priority
                        longest_wait = max(0, datetime.utcnow().timestamp() - timestamp)

                    by_tenant[tid] = {
                        "count": count,
                        "longest_wait_seconds": int(longest_wait),
                    }

        return {
            "total_queued": global_count,
            "by_tenant": by_tenant,
        }

    async def get_tenant_queue(self, tenant_id: str) -> Dict[str, Any]:
        """Get queue status for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dict with queue details
        """
        client = self._get_client()
        queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
        count = await client.zcard(queue_key)

        # Get call details
        call_ids = await client.zrange(queue_key, 0, -1)
        calls: List[Dict[str, Any]] = []
        for cid in call_ids:
            data = await client.hgetall(self.KEY_QUEUED_CALL.format(call_id=cid))
            if data:
                position = await client.zrank(queue_key, cid)
                estimate = await self.get_wait_estimate(tenant_id, (position or 0) + 1)
                calls.append(
                    {
                        "call_id": cid,
                        "caller_number": data.get("caller_number"),
                        "caller_name": data.get("caller_name"),
                        "priority": data.get("priority"),
                        "queue_entered_at": data.get("queue_entered_at"),
                        "position": (position or 0) + 1,
                        "estimated_wait_seconds": estimate,
                    }
                )

        # Calculate average wait
        avg_wait = await self.get_wait_estimate(tenant_id, 1)

        return {
            "tenant_id": tenant_id,
            "count": count,
            "avg_wait_seconds": avg_wait,
            "calls": calls,
        }

    # ---- Priority Management ----

    async def update_priority(self, call_id: str, priority: int) -> bool:
        """Manually update call priority.

        Args:
            call_id: Call identifier
            priority: New priority value

        Returns:
            True if updated
        """
        client = self._get_client()
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        if not data:
            return False

        tenant_id = data["tenant_id"]

        # Parse current score
        queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
        current_score = await client.zscore(queue_key, call_id)
        if current_score is None:
            current_score = float(f"30.{datetime.utcnow().timestamp()}")

        # Build new score with new priority but same timestamp
        timestamp_part = current_score - int(current_score)
        new_score = float(f"{priority}.{timestamp_part:.6f}".lstrip("0"))

        # Update score in queues
        await client.zadd(queue_key, {call_id: new_score})
        await client.zadd(self.KEY_GLOBAL_QUEUE, {call_id: new_score})

        # Update in hash
        await client.hset(call_key, "priority", str(priority))

        logger.info(f"Call {call_id} priority updated to {priority}")
        return True

    async def bump_priority(
        self, call_id: str, levels: int = 1
    ) -> bool:
        """Bump call priority up by N levels.

        Args:
            call_id: Call identifier
            levels: Number of priority levels to bump

        Returns:
            True if bumped
        """
        client = self._get_client()
        call_key = self.KEY_QUEUED_CALL.format(call_id=call_id)
        data = await client.hgetall(call_key)
        if not data:
            return False

        current_priority = int(data.get("priority", 30))
        new_priority = max(1, current_priority - (levels * 10))

        return await self.update_priority(call_id, new_priority)

    # ---- Wait Time Updates ----

    async def update_all_estimates(self) -> Dict[str, Any]:
        """Update wait time estimates for all queued calls.

        Called periodically by Celery beat.

        Returns:
            Dict with update statistics
        """
        client = self._get_client()
        call_ids = await client.zrange(self.KEY_GLOBAL_QUEUE, 0, -1)

        updated = 0
        for cid in call_ids:
            data = await client.hgetall(self.KEY_QUEUED_CALL.format(call_id=cid))
            if not data:
                continue

            tenant_id = data.get("tenant_id")
            if not tenant_id:
                continue

            position = await self.get_position(cid, tenant_id)
            estimate = await self.get_wait_estimate(tenant_id, position)

            await client.hset(
                self.KEY_QUEUED_CALL.format(call_id=cid),
                mapping={
                    "position": str(position),
                    "estimated_wait_seconds": str(estimate),
                },
            )
            updated += 1

        logger.debug(f"Updated wait estimates for {updated} queued calls")
        return {"updated": updated, "total_queued": len(call_ids)}

    async def record_actual_wait(
        self, call_id: str, tenant_id: str, actual_wait_seconds: float
    ) -> None:
        """Record actual wait time for a call to update EMA.

        Args:
            call_id: Call identifier
            tenant_id: Tenant identifier
            actual_wait_seconds: Actual wait time
        """
        client = self._get_client()
        key = self.KEY_STATS_AVG_WAIT.format(tenant_id=tenant_id)

        current = await client.get(key)
        if current:
            current_val = float(current)
            new_val = (
                self.EMA_ALPHA * actual_wait_seconds
                + (1 - self.EMA_ALPHA) * current_val
            )
        else:
            new_val = actual_wait_seconds

        await client.set(key, str(new_val))

        # Increment total waited counter
        total_key = self.KEY_STATS_TOTAL_WAITED.format(tenant_id=tenant_id)
        await client.incr(total_key)

        logger.debug(
            f"Recorded wait time for {call_id}: {actual_wait_seconds:.1f}s "
            f"(new EMA: {new_val:.1f}s)"
        )

    # ---- Overflow Handling ----

    async def check_overflow(self, max_queue_size: int = 50) -> Dict[str, Any]:
        """Check if queue is overflowing.

        Args:
            max_queue_size: Maximum queue size before overflow

        Returns:
            Dict with overflow status
        """
        status = await self.get_global_status()
        total = status.get("total_queued", 0)

        overflow = total > max_queue_size

        result = {
            "is_overflow": overflow,
            "total_queued": total,
            "max_size": max_queue_size,
            "overflow_count": max(0, total - max_queue_size),
        }

        if overflow:
            logger.warning(f"Queue overflow: {total} calls (max={max_queue_size})")

        return result

    async def handle_overflow(self, strategy: str = "reject_lowest") -> int:
        """Handle queue overflow by applying strategy.

        Strategies:
        - reject_lowest: Remove lowest priority calls
        - reject_oldest: Remove oldest calls

        Args:
            strategy: Overflow handling strategy

        Returns:
            Number of calls removed
        """
        client = self._get_client()
        removed = 0

        if strategy == "reject_lowest":
            # Remove lowest priority (highest score) calls from global queue
            to_remove = await client.zrevrange(
                self.KEY_GLOBAL_QUEUE, 0, 9
            )  # Remove top 10
            for call_id in to_remove:
                await self.remove_call(call_id)
                removed += 1

        elif strategy == "reject_oldest":
            # Remove oldest calls
            to_remove = await client.zrange(self.KEY_GLOBAL_QUEUE, 0, 9)
            for call_id in to_remove:
                await self.remove_call(call_id)
                removed += 1

        if removed > 0:
            logger.warning(f"Overflow handling removed {removed} calls ({strategy})")

        return removed

    # ---- Utility ----

    async def _remove_from_queues(
        self, call_id: str, tenant_id: Optional[str] = None
    ) -> None:
        """Remove call from all queue sets.

        Args:
            call_id: Call identifier
            tenant_id: Optional tenant ID for tenant queue
        """
        client = self._get_client()
        if tenant_id:
            queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
            await client.zrem(queue_key, call_id)
        await client.zrem(self.KEY_GLOBAL_QUEUE, call_id)

    async def get_queue_length(self, tenant_id: Optional[str] = None) -> int:
        """Get queue length.

        Args:
            tenant_id: Optional tenant filter

        Returns:
            Number of calls in queue
        """
        client = self._get_client()
        if tenant_id:
            queue_key = self.KEY_QUEUE.format(tenant_id=tenant_id)
            return await client.zcard(queue_key)
        return await client.zcard(self.KEY_GLOBAL_QUEUE)

    async def is_queued(self, call_id: str) -> bool:
        """Check if a call is currently in queue.

        Args:
            call_id: Call identifier

        Returns:
            True if in queue
        """
        client = self._get_client()
        score = await client.zscore(self.KEY_GLOBAL_QUEUE, call_id)
        return score is not None
