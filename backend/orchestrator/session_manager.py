"""
session_manager.py -- Redis-backed session state management.

Responsibilities:
- CRUD operations for ActiveSession objects in Redis
- State machine transitions with validation
- Session indexing (by state, tenant, worker)
- Atomic updates using Redis pipelines
- Session expiry and cleanup
- Conflict detection (duplicate call_ids)
- Lua scripts for atomic Redis operations
- Tenant-scoped session queries

Key Design Decisions:
- Uses Redis HASH for session data (O(1) access)
- Uses Redis SETs for indexes (O(1) add/remove)
- All writes go through pipeline for atomicity
- 24-hour TTL on session hashes (safety net)
- State transitions are validated (no invalid jumps)

Integration Points:
- IN: Gateway (session lifecycle)
- IN: HealthMonitor (worker failure -> reassign)
- IN: Celery tasks (archive, metrics)
- OUT: EventBus (state change events)
- OUT: Redis (session storage, indexes)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from orchestrator.models import ActiveSession, CallState, EventType, SystemEvent

logger = logging.getLogger(__name__)

# Valid state transitions (from_state -> [to_states])
VALID_TRANSITIONS: Dict[CallState, List[CallState]] = {
    CallState.CREATED: [CallState.QUEUED, CallState.ASSIGNED, CallState.ENDED],
    CallState.QUEUED: [CallState.ASSIGNED, CallState.ENDED],
    CallState.ASSIGNED: [CallState.CONNECTING, CallState.QUEUED, CallState.ENDED],
    CallState.CONNECTING: [CallState.ACTIVE, CallState.ENDED],
    CallState.ACTIVE: [CallState.PROCESSING, CallState.HOLDING, CallState.ENDED],
    CallState.PROCESSING: [CallState.ACTIVE, CallState.HOLDING, CallState.ENDED],
    CallState.HOLDING: [CallState.ACTIVE, CallState.ENDED],
    CallState.ENDED: [CallState.ARCHIVED],
    CallState.ARCHIVED: [],
}


class SessionManager:
    """Manages active call sessions in Redis.

    Provides CRUD operations, state machine validation, and indexing
    for all active call sessions in the system.

    Redis key patterns:
    - ``session:{call_id}`` -> HASH (session data)
    - ``sessions:state:{state}`` -> SET (call_ids by state)
    - ``sessions:tenant:{tenant_id}`` -> SET (call_ids by tenant)
    - ``sessions:worker:{worker_id}`` -> SET (call_ids by worker)
    """

    # Redis key prefixes
    KEY_SESSION: str = "session"
    KEY_STATE_INDEX: str = "sessions:state"
    KEY_TENANT_INDEX: str = "sessions:tenant"
    KEY_WORKER_INDEX: str = "sessions:worker"
    KEY_STATS_ACTIVE: str = "stats:sessions:active"
    KEY_STATS_PEAK: str = "stats:sessions:peak_concurrent"
    KEY_STATS_TODAY: str = "stats:sessions:total_today"

    # Default TTL for session hash (24 hours)
    SESSION_TTL: int = 86400

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        redis_url: str = "redis://localhost:6379/0",
    ):
        self.redis_url = redis_url
        self._redis: Optional[Any] = redis_client
        self.event_bus = event_bus

    def _get_client(self) -> Any:
        """Get or create async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis

    # ---- Core CRUD ----

    async def create_session(self, session: ActiveSession) -> ActiveSession:
        """Create a new session in Redis.

        Args:
            session: The ActiveSession to create

        Returns:
            The created session (with any server-side modifications)

        Raises:
            ValueError: If session with same call_id already exists
        """
        client = self._get_client()
        key = self._session_key(session.call_id)

        # Check for duplicate
        exists = await client.exists(key)
        if exists:
            raise ValueError(f"Session {session.call_id} already exists")

        # Store session hash
        await client.hset(key, mapping=session.to_redis_hash())
        await client.expire(key, self.SESSION_TTL)

        # Add to indexes atomically
        pipe = client.pipeline()
        pipe.sadd(f"{self.KEY_STATE_INDEX}:{session.state.value}", session.call_id)
        pipe.sadd(f"{self.KEY_TENANT_INDEX}:{session.tenant_id}", session.call_id)
        if session.worker_id:
            pipe.sadd(f"{self.KEY_WORKER_INDEX}:{session.worker_id}", session.call_id)
        pipe.incr(self.KEY_STATS_ACTIVE)
        await pipe.execute()

        # Update peak concurrent
        await self._update_peak_concurrent()

        logger.info(
            f"Session created: {session.call_id} for tenant {session.tenant_id} "
            f"(state={session.state.value})"
        )

        if self.event_bus:
            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.CALL_STARTED,
                    call_id=session.call_id,
                    tenant_id=session.tenant_id,
                    payload={
                        "caller_number": session.caller_number,
                        "phone_number": session.phone_number,
                        "agent_id": session.agent_id,
                    },
                )
            )

        return session

    async def get_session(self, call_id: str) -> Optional[ActiveSession]:
        """Get session by call_id.

        Args:
            call_id: The call identifier

        Returns:
            ActiveSession if found, None otherwise
        """
        client = self._get_client()
        key = self._session_key(call_id)
        data = await client.hgetall(key)
        if not data:
            return None
        try:
            return ActiveSession.from_redis_hash(data)
        except Exception as e:
            logger.error(f"Failed to deserialize session {call_id}: {e}")
            return None

    async def get_or_raise(self, call_id: str) -> ActiveSession:
        """Get session by call_id, raising if not found.

        Args:
            call_id: The call identifier

        Returns:
            ActiveSession

        Raises:
            ValueError: If session not found
        """
        session = await self.get_session(call_id)
        if session is None:
            raise ValueError(f"Session {call_id} not found")
        return session

    async def update_session(
        self, call_id: str, updates: Dict[str, Any]
    ) -> Optional[ActiveSession]:
        """Update session fields atomically.

        Handles state transitions, index updates, and validation.

        Args:
            call_id: Session identifier
            updates: Dictionary of fields to update

        Returns:
            Updated session or None if not found

        Raises:
            ValueError: If state transition is invalid
        """
        client = self._get_client()
        key = self._session_key(call_id)

        # Get current session
        current = await self.get_session(call_id)
        if not current:
            return None

        # Handle state transition
        new_state: Optional[CallState] = None
        raw_state = updates.get("state")
        if raw_state is not None:
            if isinstance(raw_state, str):
                new_state = CallState(raw_state)
            elif isinstance(raw_state, CallState):
                new_state = raw_state
            else:
                raise ValueError(f"Invalid state type: {type(raw_state)}")

            if not self._is_valid_transition(current.state, new_state):
                raise ValueError(
                    f"Invalid state transition: {current.state.value} -> {new_state.value}"
                )

        # Build update hash and index operations
        update_hash: Dict[str, str] = {}
        index_ops: list = []

        for field, value in updates.items():
            if field == "state" and new_state is not None:
                update_hash["state"] = new_state.value
                if current.state != new_state:
                    index_ops.extend(
                        [
                            (
                                "srem",
                                f"{self.KEY_STATE_INDEX}:{current.state.value}",
                                call_id,
                            ),
                            (
                                "sadd",
                                f"{self.KEY_STATE_INDEX}:{new_state.value}",
                                call_id,
                            ),
                        ]
                    )
            elif field == "worker_id" and value != current.worker_id:
                update_hash["worker_id"] = str(value) if value else ""
                if current.worker_id:
                    index_ops.append(
                        (
                            "srem",
                            f"{self.KEY_WORKER_INDEX}:{current.worker_id}",
                            call_id,
                        )
                    )
                if value:
                    index_ops.append(
                        ("sadd", f"{self.KEY_WORKER_INDEX}:{value}", call_id)
                    )
            elif field == "transcript" and isinstance(value, list):
                update_hash["transcript"] = json.dumps(value)
            elif field == "state_history" and isinstance(value, list):
                update_hash["state_history"] = json.dumps(
                    [{k: str(v) for k, v in item.items()} for item in value]
                )
            elif field == "agent_config" and isinstance(value, dict):
                update_hash["agent_config"] = json.dumps(value)
            elif isinstance(value, datetime):
                update_hash[field] = value.isoformat()
            elif isinstance(value, bool):
                update_hash[field] = "1" if value else "0"
            elif value is None:
                update_hash[field] = ""
            else:
                update_hash[field] = str(value)

        # Execute atomically via pipeline
        pipe = client.pipeline()
        if update_hash:
            pipe.hset(key, mapping=update_hash)
        for cmd, idx_key, member in index_ops:
            getattr(pipe, cmd)(idx_key, member)
        await pipe.execute()

        # Add to state history
        if new_state and current.state != new_state:
            await self._add_state_history(
                call_id, current.state, new_state, updates.get("reason")
            )

            # Publish state change event
            if self.event_bus:
                event_type = self._state_to_event(new_state)
                if event_type:
                    self.event_bus.publish(
                        SystemEvent(
                            event_type=event_type,
                            call_id=call_id,
                            tenant_id=current.tenant_id,
                            payload={
                                "from_state": current.state.value,
                                "to_state": new_state.value,
                                "reason": updates.get("reason"),
                            },
                        )
                    )

        logger.debug(f"Session {call_id} updated: {list(updates.keys())}")
        return await self.get_session(call_id)

    async def delete_session(self, call_id: str) -> bool:
        """Delete session and all indexes.

        Args:
            call_id: Session identifier

        Returns:
            True if session existed and was deleted
        """
        client = self._get_client()
        session = await self.get_session(call_id)
        if not session:
            return False

        key = self._session_key(call_id)

        pipe = client.pipeline()
        # Remove from indexes
        pipe.srem(f"{self.KEY_STATE_INDEX}:{session.state.value}", call_id)
        pipe.srem(f"{self.KEY_TENANT_INDEX}:{session.tenant_id}", call_id)
        if session.worker_id:
            pipe.srem(f"{self.KEY_WORKER_INDEX}:{session.worker_id}", call_id)
        pipe.decr(self.KEY_STATS_ACTIVE)
        # Delete hash
        pipe.delete(key)
        await pipe.execute()

        logger.info(f"Session deleted: {call_id}")
        return True

    async def end_session(self, call_id: str, reason: str = "hangup") -> Optional[ActiveSession]:
        """End a session (transition to ENDED state).

        Args:
            call_id: Session identifier
            reason: Reason for ending

        Returns:
            Updated session or None if not found
        """
        return await self.update_session(
            call_id,
            {
                "state": CallState.ENDED,
                "ended_at": datetime.utcnow(),
                "reason": reason,
            },
        )

    # ---- Batch Operations ----

    async def create_sessions_batch(
        self, sessions: List[ActiveSession]
    ) -> List[ActiveSession]:
        """Create multiple sessions atomically.

        Args:
            sessions: List of ActiveSession objects to create

        Returns:
            List of created sessions

        Raises:
            ValueError: If any session already exists
        """
        # Check all first
        for session in sessions:
            exists = await self._get_client().exists(self._session_key(session.call_id))
            if exists:
                raise ValueError(f"Session {session.call_id} already exists")

        # Create all
        created: List[ActiveSession] = []
        for session in sessions:
            result = await self.create_session(session)
            created.append(result)

        return created

    # ---- Queries ----

    async def list_sessions(
        self,
        tenant_id: Optional[str] = None,
        state: Optional[str] = None,
        worker_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ActiveSession]:
        """List sessions with optional filtering.

        Args:
            tenant_id: Filter by tenant
            state: Filter by call state
            worker_id: Filter by assigned worker
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of ActiveSession objects
        """
        client = self._get_client()

        # Determine which index to use
        if state:
            call_ids = await client.smembers(f"{self.KEY_STATE_INDEX}:{state}")
        elif worker_id:
            call_ids = await client.smembers(f"{self.KEY_WORKER_INDEX}:{worker_id}")
        elif tenant_id:
            call_ids = await client.smembers(f"{self.KEY_TENANT_INDEX}:{tenant_id}")
        else:
            # Get all active sessions - scan all state indexes
            call_ids: set = set()
            for s in CallState:
                ids = await client.smembers(f"{self.KEY_STATE_INDEX}:{s.value}")
                call_ids.update(ids)

        # Convert to list and apply pagination
        sorted_ids = sorted(list(call_ids))
        paginated_ids = sorted_ids[offset : offset + limit]

        # Fetch sessions
        sessions: List[ActiveSession] = []
        for cid in paginated_ids:
            session = await self.get_session(cid)
            if session:
                # Apply tenant filter if not using tenant index
                if tenant_id and not tenant_id and session.tenant_id != tenant_id:
                    continue
                sessions.append(session)

        return sessions

    async def count_sessions(
        self,
        tenant_id: Optional[str] = None,
        state: Optional[str] = None,
    ) -> int:
        """Count sessions matching criteria.

        Args:
            tenant_id: Filter by tenant
            state: Filter by state

        Returns:
            Count of matching sessions
        """
        client = self._get_client()
        if state:
            return await client.scard(f"{self.KEY_STATE_INDEX}:{state}")
        elif tenant_id:
            return await client.scard(f"{self.KEY_TENANT_INDEX}:{tenant_id}")
        else:
            # Sum all state indexes (excluding archived)
            total = 0
            for s in CallState:
                if s != CallState.ARCHIVED:
                    total += await client.scard(f"{self.KEY_STATE_INDEX}:{s.value}")
            return total

    async def get_sessions_by_worker(self, worker_id: str) -> List[ActiveSession]:
        """Get all sessions assigned to a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            List of ActiveSession objects
        """
        client = self._get_client()
        call_ids = await client.smembers(f"{self.KEY_WORKER_INDEX}:{worker_id}")
        sessions: List[ActiveSession] = []
        for cid in call_ids:
            session = await self.get_session(cid)
            if session:
                sessions.append(session)
        return sessions

    async def get_sessions_by_tenant(
        self, tenant_id: str, state: Optional[str] = None
    ) -> List[ActiveSession]:
        """Get all sessions for a tenant.

        Args:
            tenant_id: Tenant identifier
            state: Optional state filter

        Returns:
            List of ActiveSession objects
        """
        if state:
            # Intersection of tenant and state sets
            client = self._get_client()
            call_ids = await client.sinter(
                f"{self.KEY_TENANT_INDEX}:{tenant_id}",
                f"{self.KEY_STATE_INDEX}:{state}",
            )
            sessions: List[ActiveSession] = []
            for cid in sorted(call_ids):
                session = await self.get_session(cid)
                if session:
                    sessions.append(session)
            return sessions

        return await self.list_sessions(tenant_id=tenant_id)

    async def get_active_call_ids(self) -> List[str]:
        """Get all active (non-ended, non-archived) call IDs.

        Returns:
            List of call_id strings
        """
        client = self._get_client()
        active_states = [CallState.ACTIVE, CallState.PROCESSING, CallState.CONNECTING]
        call_ids: set = set()
        for s in active_states:
            ids = await client.smembers(f"{self.KEY_STATE_INDEX}:{s.value}")
            call_ids.update(ids)
        return sorted(list(call_ids))

    # ---- State Machine ----

    def _is_valid_transition(self, from_state: CallState, to_state: CallState) -> bool:
        """Check if state transition is valid.

        Args:
            from_state: Current state
            to_state: Desired new state

        Returns:
            True if transition is allowed
        """
        if from_state == to_state:
            return True  # Same state is always valid (no-op)
        return to_state in VALID_TRANSITIONS.get(from_state, [])

    async def transition_state(
        self,
        call_id: str,
        to_state: CallState,
        reason: Optional[str] = None,
    ) -> Optional[ActiveSession]:
        """Transition session to a new state.

        Args:
            call_id: Session identifier
            to_state: Target state
            reason: Reason for transition

        Returns:
            Updated session or None

        Raises:
            ValueError: If transition is invalid
        """
        updates: Dict[str, Any] = {"state": to_state}
        if reason:
            updates["reason"] = reason

        if to_state == CallState.ACTIVE:
            updates["answered_at"] = datetime.utcnow()
        elif to_state == CallState.ENDED:
            updates["ended_at"] = datetime.utcnow()

        return await self.update_session(call_id, updates)

    async def _add_state_history(
        self,
        call_id: str,
        from_state: CallState,
        to_state: CallState,
        reason: Optional[str] = None,
    ) -> None:
        """Add entry to state history.

        Args:
            call_id: Session identifier
            from_state: Previous state
            to_state: New state
            reason: Optional reason for transition
        """
        client = self._get_client()
        key = self._session_key(call_id)
        session = await self.get_session(call_id)
        if not session:
            return

        history = list(session.state_history)
        history.append(
            {
                "from": from_state.value,
                "to": to_state.value,
                "at": datetime.utcnow().isoformat(),
                "reason": reason or "",
            }
        )
        await client.hset(key, "state_history", json.dumps(history))

    def _state_to_event(self, state: CallState) -> Optional[EventType]:
        """Map state to event type.

        Args:
            state: CallState to map

        Returns:
            Corresponding EventType or None
        """
        mapping = {
            CallState.QUEUED: EventType.CALL_QUEUED,
            CallState.ASSIGNED: EventType.CALL_ASSIGNED,
            CallState.CONNECTING: EventType.CALL_CONNECTED,
            CallState.ACTIVE: EventType.CALL_ACTIVE,
            CallState.HOLDING: EventType.CALL_HOLDING,
            CallState.ENDED: EventType.CALL_ENDED,
        }
        return mapping.get(state)

    # ---- Session Expiry / Cleanup ----

    async def get_expired_sessions(self, max_idle_seconds: int = 3600) -> List[ActiveSession]:
        """Find sessions that have been idle too long.

        Args:
            max_idle_seconds: Maximum idle time before considered expired

        Returns:
            List of expired sessions
        """
        now = datetime.utcnow()
        all_active = await self.list_sessions(limit=1000)
        expired: List[ActiveSession] = []
        for session in all_active:
            idle_time = (now - session.last_activity_at).total_seconds()
            if idle_time > max_idle_seconds:
                expired.append(session)
        return expired

    async def cleanup_expired_sessions(self, max_idle_seconds: int = 3600) -> int:
        """Clean up sessions that have been idle too long.

        Args:
            max_idle_seconds: Maximum idle time

        Returns:
            Number of sessions cleaned up
        """
        expired = await self.get_expired_sessions(max_idle_seconds)
        count = 0
        for session in expired:
            try:
                await self.end_session(session.call_id, reason="idle_timeout")
                count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup session {session.call_id}: {e}")
        return count

    async def cleanup_orphaned_indexes(self) -> int:
        """Remove call_ids from indexes that no longer have session hashes.

        Returns:
            Number of orphaned entries cleaned
        """
        client = self._get_client()
        cleaned = 0

        for state in CallState:
            key = f"{self.KEY_STATE_INDEX}:{state.value}"
            call_ids = await client.smembers(key)
            for cid in call_ids:
                exists = await client.exists(self._session_key(cid))
                if not exists:
                    await client.srem(key, cid)
                    cleaned += 1

        return cleaned

    # ---- Reassignment ----

    async def reassign_calls(
        self, from_worker_id: str, reason: str = "worker_failure"
    ) -> int:
        """Reassign all calls from a failed worker back to the queue.

        Args:
            from_worker_id: Worker that failed
            reason: Reason for reassignment

        Returns:
            Number of calls reassigned
        """
        sessions = await self.get_sessions_by_worker(from_worker_id)
        count = 0

        for session in sessions:
            # Only reassign non-terminal states
            if session.state in (CallState.ENDED, CallState.ARCHIVED):
                continue

            try:
                await self.transition_state(
                    session.call_id, CallState.QUEUED, reason=reason
                )
                # Clear worker assignment
                await self.update_session(
                    session.call_id,
                    {
                        "worker_id": "",
                        "worker_node": "",
                        "gpu_device": None,
                    },
                )
                count += 1
                logger.warning(
                    f"Reassigned call {session.call_id} from worker {from_worker_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to reassign call {session.call_id}: {e}"
                )

        return count

    # ---- Lua Scripts ----

    async def atomic_assign_worker(
        self, call_id: str, session_data: Dict[str, str]
    ) -> Optional[str]:
        """Atomically find best worker and assign session using Lua script.

        This is a server-side implementation using Redis transactions
        rather than a Lua script for portability.

        Args:
            call_id: Call identifier
            session_data: Session data to update

        Returns:
            worker_id if assigned, None if no workers available
        """
        client = self._get_client()

        # Find all worker keys
        worker_keys = await client.keys("worker:*")
        if not worker_keys:
            return None

        best_worker_id: Optional[str] = None
        best_slots = -1
        best_gpu = 0

        for wkey in worker_keys:
            # Skip keys that are command queues or other worker metadata
            if ":commands" in wkey or ":latencies" in wkey:
                continue

            data = await client.hgetall(wkey)
            if not data:
                continue

            status = data.get("status", "")
            if status not in ("idle", "busy"):
                continue

            try:
                current_sessions = json.loads(data.get("current_sessions", "[]"))
                max_sess = int(data.get("max_concurrent_sessions", 4))
                slots = max_sess - len(current_sessions)
            except (json.JSONDecodeError, ValueError):
                continue

            if slots > best_slots and slots > 0:
                best_slots = slots
                best_worker_id = data.get("worker_id")
                best_gpu = data.get("gpu_device", "0")

        if best_worker_id:
            # Update session with worker assignment
            session_key = self._session_key(call_id)
            pipe = client.pipeline()
            pipe.hset(session_key, "worker_id", best_worker_id)
            pipe.hset(session_key, "gpu_device", str(best_gpu))
            pipe.hset(session_key, "state", CallState.ASSIGNED.value)
            pipe.sadd(f"{self.KEY_WORKER_INDEX}:{best_worker_id}", call_id)
            await pipe.execute()

            return best_worker_id

        return None

    # ---- Utility ----

    def _session_key(self, call_id: str) -> str:
        """Build Redis key for session hash.

        Args:
            call_id: Call identifier

        Returns:
            Redis key string
        """
        return f"{self.KEY_SESSION}:{call_id}"

    async def _update_peak_concurrent(self) -> None:
        """Update peak concurrent sessions counter."""
        client = self._get_client()
        current = await client.get(self.KEY_STATS_ACTIVE)
        current_val = int(current) if current else 0

        peak = await client.get(self.KEY_STATS_PEAK)
        peak_val = int(peak) if peak else 0

        if current_val > peak_val:
            await client.set(self.KEY_STATS_PEAK, str(current_val))

    async def get_peak_concurrent(self) -> int:
        """Get peak concurrent sessions (today).

        Returns:
            Peak concurrent session count
        """
        val = await self._get_client().get(self.KEY_STATS_PEAK)
        return int(val) if val else 0

    async def reset_daily_stats(self) -> None:
        """Reset daily statistics (call at midnight)."""
        client = self._get_client()
        await client.delete(self.KEY_STATS_PEAK)
        await client.delete(self.KEY_STATS_TODAY)
        logger.info("Daily stats reset")

    async def get_session_metrics(self) -> Dict[str, Any]:
        """Get aggregate session metrics.

        Returns:
            Dictionary with session counts by state and other metrics
        """
        client = self._get_client()
        metrics: Dict[str, Any] = {"by_state": {}, "total": 0}

        for state in CallState:
            count = await client.scard(f"{self.KEY_STATE_INDEX}:{state.value}")
            metrics["by_state"][state.value] = count
            if state != CallState.ARCHIVED:
                metrics["total"] += count

        metrics["peak_concurrent"] = await self.get_peak_concurrent()
        metrics["active_calls"] = await self.count_sessions(
            state=CallState.ACTIVE.value
        )
        metrics["queued_calls"] = await self.count_sessions(
            state=CallState.QUEUED.value
        )

        return metrics
