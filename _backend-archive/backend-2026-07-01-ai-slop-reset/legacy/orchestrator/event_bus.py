"""
event_bus.py -- Redis pub/sub event bus for inter-service communication.

Responsibilities:
- Publish events to Redis pub/sub channels
- Subscribe to events with optional filtering
- Persist events to Redis Stream for replay
- Provide event history queries
- Fan-out events to WebSocket subscribers
- Dead letter queue for failed events
- Event replay capability

Event Channels:
- events:all          -- All events (broadcast)
- events:call:{id}    -- Events for specific call
- events:worker:{id}  -- Events for specific worker
- events:tenant:{id}  -- Events for specific tenant
- events:type:{type}  -- Events of specific type

Integration Points:
- IN: SessionManager, WorkerPool, HealthMonitor, Gateway
- OUT: WebSocket subscribers (dashboard)
- OUT: Celery tasks (event-driven triggers)
- OUT: PostgreSQL (event archiving)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set

import redis.asyncio as aioredis

from legacy.orchestrator.models import EventType, SystemEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Redis-backed event bus for inter-service communication.

    Uses multiple Redis features:
    - Pub/Sub for real-time event broadcasting
    - Streams for persistent event log (replay)
    - Lists for recent event indexing
    """

    # Redis pub/sub channels
    CHANNEL_ALL: str = "events:all"
    CHANNEL_CALL_TEMPLATE: str = "events:call:{call_id}"
    CHANNEL_WORKER_TEMPLATE: str = "events:worker:{worker_id}"
    CHANNEL_TENANT_TEMPLATE: str = "events:tenant:{tenant_id}"
    CHANNEL_TYPE_TEMPLATE: str = "events:type:{event_type}"

    # Redis Stream for persistence
    STREAM_KEY: str = "event_stream"
    STREAM_MAXLEN: int = 10000

    # Recent events list
    RECENT_KEY_TEMPLATE: str = "events:recent:{event_type}"
    RECENT_MAX: int = 100

    # Per-call event log
    CALL_EVENTS_TEMPLATE: str = "events:call:{call_id}"
    CALL_EVENTS_MAX: int = 1000
    CALL_EVENTS_TTL: int = 86400  # 24 hours

    # Dead letter queue
    DLQ_KEY: str = "events:dlq"
    DLQ_MAXLEN: int = 5000

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        redis_url: str = "redis://localhost:6379/0",
    ):
        self.redis_url = redis_url
        self._redis: Optional[Any] = redis_client
        self._subscribers: Set[asyncio.Queue] = set()
        self._listener_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._event_handlers: Dict[EventType, List[Callable]] = {}

    def _get_client(self) -> Any:
        """Get or create async Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def _ensure_client(self) -> Any:
        """Ensure Redis client is available."""
        return self._get_client()

    # ---- Publishing ----

    def publish(self, event: SystemEvent) -> bool:
        """Publish an event (async fire-and-forget).

        Schedules the actual publish in the event loop.

        Args:
            event: The SystemEvent to publish

        Returns:
            True if scheduled successfully
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._do_publish(event))
            else:
                loop.run_until_complete(self._do_publish(event))
            return True
        except Exception as e:
            logger.error(f"Failed to schedule publish for event {event.event_id}: {e}")
            return False

    async def _do_publish(self, event: SystemEvent) -> bool:
        """Internal: publish event to all channels and persist."""
        try:
            client = await self._ensure_client()
            event_json = event.to_json()

            # Build channel list
            channels = [self.CHANNEL_ALL]
            if event.call_id:
                channels.append(
                    self.CHANNEL_CALL_TEMPLATE.format(call_id=event.call_id)
                )
            if event.worker_id:
                channels.append(
                    self.CHANNEL_WORKER_TEMPLATE.format(worker_id=event.worker_id)
                )
            if event.tenant_id:
                channels.append(
                    self.CHANNEL_TENANT_TEMPLATE.format(tenant_id=event.tenant_id)
                )
            channels.append(
                self.CHANNEL_TYPE_TEMPLATE.format(event_type=event.event_type.value)
            )

            # Publish to all channels via pipeline
            pipe = client.pipeline()
            for channel in channels:
                pipe.publish(channel, event_json)

            # Persist to stream
            pipe.xadd(
                self.STREAM_KEY,
                {
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "call_id": event.call_id or "",
                    "worker_id": event.worker_id or "",
                    "tenant_id": event.tenant_id or "",
                    "payload": json.dumps(event.payload),
                    "event_json": event_json,
                },
                maxlen=self.STREAM_MAXLEN,
                approximate=True,
            )

            # Add to recent events list
            recent_key = self.RECENT_KEY_TEMPLATE.format(
                event_type=event.event_type.value
            )
            pipe.lpush(recent_key, event_json)
            pipe.ltrim(recent_key, 0, self.RECENT_MAX - 1)

            # Add to per-call event log
            if event.call_id:
                call_key = self.CALL_EVENTS_TEMPLATE.format(call_id=event.call_id)
                pipe.lpush(call_key, event_json)
                pipe.ltrim(call_key, 0, self.CALL_EVENTS_MAX - 1)
                pipe.expire(call_key, self.CALL_EVENTS_TTL)

            await pipe.execute()

            # Notify local subscribers (in-process WebSocket connections)
            self._notify_local_subscribers(event)

            # Invoke registered handlers
            await self._invoke_handlers(event)

            return True

        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            await self._dlq_put(event, str(e))
            return False

    async def publish_async(self, event: SystemEvent) -> bool:
        """Publish an event (async awaitable version)."""
        return await self._do_publish(event)

    def publish_sync(self, event: SystemEvent) -> bool:
        """Synchronous version of publish for use in Celery tasks.

        Creates a fresh synchronous Redis connection.
        """
        import redis as sync_redis

        client: Optional[sync_redis.Redis] = None
        try:
            client = sync_redis.from_url(self.redis_url, decode_responses=True)
            event_json = event.to_json()

            channels = [self.CHANNEL_ALL]
            if event.call_id:
                channels.append(
                    self.CHANNEL_CALL_TEMPLATE.format(call_id=event.call_id)
                )
            if event.worker_id:
                channels.append(
                    self.CHANNEL_WORKER_TEMPLATE.format(worker_id=event.worker_id)
                )
            if event.tenant_id:
                channels.append(
                    self.CHANNEL_TENANT_TEMPLATE.format(tenant_id=event.tenant_id)
                )
            channels.append(
                self.CHANNEL_TYPE_TEMPLATE.format(event_type=event.event_type.value)
            )

            pipe = client.pipeline()
            for channel in channels:
                pipe.publish(channel, event_json)

            pipe.xadd(
                self.STREAM_KEY,
                {
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "call_id": event.call_id or "",
                    "worker_id": event.worker_id or "",
                    "tenant_id": event.tenant_id or "",
                    "payload": json.dumps(event.payload),
                    "event_json": event_json,
                },
                maxlen=self.STREAM_MAXLEN,
                approximate=True,
            )

            recent_key = self.RECENT_KEY_TEMPLATE.format(
                event_type=event.event_type.value
            )
            pipe.lpush(recent_key, event_json)
            pipe.ltrim(recent_key, 0, self.RECENT_MAX - 1)

            if event.call_id:
                call_key = self.CALL_EVENTS_TEMPLATE.format(call_id=event.call_id)
                pipe.lpush(call_key, event_json)
                pipe.ltrim(call_key, 0, self.CALL_EVENTS_MAX - 1)
                pipe.expire(call_key, self.CALL_EVENTS_TTL)

            pipe.execute()
            return True

        except Exception as e:
            logger.error(f"Failed to sync publish event: {e}")
            return False
        finally:
            if client:
                client.close()

    # ---- Local Subscribing (in-process) ----

    async def subscribe(
        self,
        filter_types: Optional[Set[str]] = None,
        filter_tenant: Optional[str] = None,
        filter_call: Optional[str] = None,
    ) -> AsyncIterator[SystemEvent]:
        """Subscribe to events with optional filtering.

        This is an async generator that yields matching events.
        Used by WebSocket handlers to stream events to clients.

        Args:
            filter_types: Set of event type strings to include
            filter_tenant: Only events for this tenant
            filter_call: Only events for this call

        Yields:
            SystemEvent objects matching filters
        """
        queue: asyncio.Queue[SystemEvent] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    continue

                # Apply filters
                if filter_types and event.event_type.value not in filter_types:
                    continue
                if filter_tenant and event.tenant_id != filter_tenant:
                    continue
                if filter_call and event.call_id != filter_call:
                    continue

                yield event

        finally:
            self._subscribers.discard(queue)

    def _notify_local_subscribers(self, event: SystemEvent) -> None:
        """Notify local (in-process) subscribers."""
        dead_queues: List[asyncio.Queue] = []
        for queue in self._subscribers:
            try:
                if queue.full():
                    dead_queues.append(queue)
                    continue
                # Schedule the put without awaiting
                asyncio.get_event_loop().call_soon(
                    lambda q=queue, e=event: asyncio.create_task(q.put(e))
                )
            except Exception:
                dead_queues.append(queue)

        # Clean up dead/full queues
        for dq in dead_queues:
            self._subscribers.discard(dq)

    # ---- Event Handlers ----

    def on(self, event_type: EventType, handler: Callable) -> None:
        """Register an event handler.

        Args:
            event_type: Event type to listen for
            handler: Async or sync callable that receives SystemEvent
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: Callable) -> None:
        """Unregister an event handler."""
        if event_type in self._event_handlers:
            self._event_handlers[event_type] = [
                h for h in self._event_handlers[event_type] if h != handler
            ]

    async def _invoke_handlers(self, event: SystemEvent) -> None:
        """Invoke registered handlers for an event."""
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type}: {e}")

    # ---- Redis Pub/Sub Background Listener ----

    async def start_listener(self) -> None:
        """Start background listener for Redis pub/sub.

        Listens on events:all channel and forwards to local subscribers.
        """
        if self._running:
            return

        self._running = True
        self._listener_task = asyncio.create_task(self._listener_loop())
        logger.info("Event bus listener started")

    async def stop_listener(self) -> None:
        """Stop background listener."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        logger.info("Event bus listener stopped")

    async def _listener_loop(self) -> None:
        """Background task listening for Redis pub/sub messages."""
        client = await self._ensure_client()
        while self._running:
            try:
                pubsub = client.pubsub()
                await pubsub.subscribe(self.CHANNEL_ALL)

                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] == "message":
                        try:
                            event = SystemEvent.from_json(message["data"])
                            self._notify_local_subscribers(event)
                        except Exception as e:
                            logger.error(f"Error parsing pub/sub event: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event bus listener error: {e}")
                await asyncio.sleep(1)  # Reconnect delay

    # ---- Event History / Replay ----

    async def get_recent_events(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[SystemEvent]:
        """Get recent events from Redis.

        Args:
            event_type: Filter by event type (optional)
            limit: Maximum events to return

        Returns:
            List of SystemEvent objects (most recent first)
        """
        client = await self._ensure_client()
        if event_type:
            key = self.RECENT_KEY_TEMPLATE.format(event_type=event_type)
            events_json = await client.lrange(key, 0, limit - 1)
        else:
            # Get from stream
            entries = await client.xrevrange(self.STREAM_KEY, count=limit)
            events_json = [entry[1].get("event_json", "") for entry in entries]

        events: List[SystemEvent] = []
        for ejson in events_json:
            if not ejson:
                continue
            try:
                events.append(SystemEvent.from_json(ejson))
            except Exception:
                pass
        return events

    async def get_call_events(
        self, call_id: str, limit: int = 100
    ) -> List[SystemEvent]:
        """Get events for a specific call."""
        client = await self._ensure_client()
        key = self.CALL_EVENTS_TEMPLATE.format(call_id=call_id)
        events_json = await client.lrange(key, 0, limit - 1)

        events: List[SystemEvent] = []
        for ejson in events_json:
            try:
                events.append(SystemEvent.from_json(ejson))
            except Exception:
                pass
        return events

    async def get_stream_events(
        self, start_id: str = "0", count: int = 100
    ) -> List[Dict[str, Any]]:
        """Read events from Redis Stream (for replay).

        Args:
            start_id: Stream ID to start from ("0" for beginning, "$" for latest)
            count: Maximum number of events

        Returns:
            List of event dictionaries with metadata
        """
        client = await self._ensure_client()
        entries = await client.xrange(self.STREAM_KEY, min=start_id, count=count)
        return [
            {
                "id": entry[0],
                "event_type": entry[1].get("event_type"),
                "timestamp": entry[1].get("timestamp"),
                "call_id": entry[1].get("call_id"),
                "worker_id": entry[1].get("worker_id"),
                "tenant_id": entry[1].get("tenant_id"),
                "payload": json.loads(entry[1].get("payload", "{}")),
            }
            for entry in entries
        ]

    async def replay_events(
        self,
        start_id: str = "0",
        event_types: Optional[Set[str]] = None,
        handler: Optional[Callable[[SystemEvent], Any]] = None,
    ) -> int:
        """Replay events from Redis Stream.

        Args:
            start_id: Stream ID to start from
            event_types: Optional set of event types to filter
            handler: Optional handler to invoke for each event

        Returns:
            Number of events replayed
        """
        count = 0
        async for batch in self._replay_batches(start_id):
            for entry in batch:
                event_data = entry[1]
                if event_types and event_data.get("event_type") not in event_types:
                    continue

                count += 1
                if handler:
                    try:
                        event = SystemEvent.from_json(
                            event_data.get("event_json", "{}")
                        )
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Replay handler error: {e}")
        return count

    async def _replay_batches(
        self, start_id: str, batch_size: int = 100
    ) -> AsyncIterator[List]:
        """Yield batches of stream entries for replay."""
        current_id = start_id
        while True:
            entries = await self.get_stream_events(current_id, batch_size)
            if not entries:
                break
            # Convert back to stream entry format for consistency
            client = await self._ensure_client()
            raw = await client.xrange(
                self.STREAM_KEY, min=current_id, count=batch_size + 1
            )
            if not raw or (len(raw) == 1 and raw[0][0] == current_id):
                break
            # Skip the first entry if it's the same as start_id
            batch = [e for e in raw if e[0] != current_id]
            if not batch:
                break
            yield batch
            current_id = batch[-1][0]

    # ---- Dead Letter Queue ----

    async def _dlq_put(self, event: SystemEvent, error: str) -> None:
        """Put a failed event into the dead letter queue."""
        try:
            client = await self._ensure_client()
            entry = {
                "event_json": event.to_json(),
                "error": error,
                "failed_at": datetime.utcnow().isoformat(),
            }
            await client.xadd(
                self.DLQ_KEY,
                entry,
                maxlen=self.DLQ_MAXLEN,
                approximate=True,
            )
        except Exception as e:
            logger.error(f"Failed to write to DLQ: {e}")

    async def get_dlq_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get events from the dead letter queue."""
        client = await self._ensure_client()
        entries = await client.xrevrange(self.DLQ_KEY, count=count)
        return [
            {
                "id": entry[0],
                "event_json": entry[1].get("event_json"),
                "error": entry[1].get("error"),
                "failed_at": entry[1].get("failed_at"),
            }
            for entry in entries
        ]

    async def dlq_reprocess(
        self, event_id: Optional[str] = None, handler: Optional[Callable] = None
    ) -> int:
        """Reprocess events from the dead letter queue.

        Args:
            event_id: Specific DLQ event ID to reprocess, or None for all
            handler: Optional handler to process the event

        Returns:
            Number of events reprocessed
        """
        client = await self._ensure_client()
        count = 0

        if event_id:
            entries = [(event_id, await client.xrange(self.DLQ_KEY, min=event_id, count=1))]
        else:
            entries_raw = await client.xrange(self.DLQ_KEY)
            entries = [(e[0], [e]) for e in entries_raw]

        for dlq_id, entry_list in entries:
            for entry in entry_list:
                try:
                    event_data = entry[1]
                    event = SystemEvent.from_json(event_data.get("event_json", "{}"))

                    # Re-publish
                    await self.publish_async(event)

                    if handler:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)

                    # Remove from DLQ
                    await client.xdel(self.DLQ_KEY, dlq_id)
                    count += 1

                except Exception as e:
                    logger.error(f"DLQ reprocess failed for {dlq_id}: {e}")

        return count
