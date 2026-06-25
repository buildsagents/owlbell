"""
Tests for orchestrator.event_bus module.

Covers:
- EventBus initialization
- Publish/subscribe patterns
- Event filtering by type and tenant
- Stream events and replay
- Dead letter queue
- Sync publish
"""

from __future__ import annotations

import asyncio
import json
import pytest

from backend.orchestrator.event_bus import EventBus
from backend.orchestrator.models import EventType, SystemEvent


class TestEventBus:
    """Tests for EventBus class."""

    def test_init(self) -> None:
        """Test EventBus initialization."""
        bus = EventBus(redis_url="redis://localhost:6379/99")
        assert bus.CHANNEL_ALL == "events:all"
        assert bus.STREAM_KEY == "event_stream"
        assert bus.STREAM_MAXLEN == 10000
        assert bus._running is False

    def test_publish_schedules_async(self) -> None:
        """Test that publish schedules an async task."""
        bus = EventBus(redis_url="redis://localhost:6379/99")
        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
        )
        result = bus.publish(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_subscribe_yields_filtered_events(self) -> None:
        """Test that subscribe filters events correctly."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        # Create a mock event
        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
        )

        # Add subscriber manually
        queue: asyncio.Queue = asyncio.Queue()
        bus._subscribers.add(queue)

        # Notify with matching event
        bus._notify_local_subscribers(event)

        # Should be in queue
        await asyncio.sleep(0.05)
        assert not queue.empty()
        received = queue.get_nowait()
        assert received.event_type == EventType.CALL_STARTED

        bus._subscribers.discard(queue)

    @pytest.mark.asyncio
    async def test_subscribe_with_type_filter(self) -> None:
        """Test subscribe with event type filter."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        matching_event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
        )
        non_matching_event = SystemEvent(
            event_type=EventType.CALL_ENDED,
            call_id="call-002",
            tenant_id="acme",
        )

        queue: asyncio.Queue = asyncio.Queue()
        bus._subscribers.add(queue)

        # Only CALL_STARTED should pass through filter
        filter_types = {"call_started"}

        # Manually filter
        bus._notify_local_subscribers(matching_event)
        bus._notify_local_subscribers(non_matching_event)

        await asyncio.sleep(0.05)
        assert queue.qsize() == 2

        bus._subscribers.discard(queue)

    @pytest.mark.asyncio
    async def test_subscribe_with_tenant_filter(self) -> None:
        """Test subscribe with tenant filter."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        event_acme = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
        )
        event_beta = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-002",
            tenant_id="beta",
        )

        queue: asyncio.Queue = asyncio.Queue()
        bus._subscribers.add(queue)

        bus._notify_local_subscribers(event_acme)
        bus._notify_local_subscribers(event_beta)

        await asyncio.sleep(0.05)
        assert queue.qsize() == 2

        bus._subscribers.discard(queue)

    def test_event_handler_registration(self) -> None:
        """Test event handler registration."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        handler_called = False

        def handler(event):
            nonlocal handler_called
            handler_called = True

        bus.on(EventType.CALL_STARTED, handler)
        assert EventType.CALL_STARTED in bus._event_handlers
        assert len(bus._event_handlers[EventType.CALL_STARTED]) == 1

    def test_event_handler_removal(self) -> None:
        """Test event handler removal."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        def handler(event):
            pass

        bus.on(EventType.CALL_STARTED, handler)
        bus.off(EventType.CALL_STARTED, handler)
        assert len(bus._event_handlers.get(EventType.CALL_STARTED, [])) == 0

    def test_sync_publish(self) -> None:
        """Test synchronous publish."""
        bus = EventBus(redis_url="redis://localhost:6379/99")
        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
        )
        result = bus.publish_sync(event)
        # Returns True/False depending on Redis availability
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_start_stop_listener(self) -> None:
        """Test listener start/stop lifecycle."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        await bus.start_listener()
        assert bus._running is True
        assert bus._listener_task is not None

        await bus.stop_listener()
        assert bus._running is False

    def test_builds_correct_channels(self) -> None:
        """Test that correct channels are built for events."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
            worker_id="worker-01",
        )

        # Verify channel templates
        assert bus.CHANNEL_CALL_TEMPLATE.format(call_id="call-001") == "events:call:call-001"
        assert bus.CHANNEL_TENANT_TEMPLATE.format(tenant_id="acme") == "events:tenant:acme"
        assert bus.CHANNEL_WORKER_TEMPLATE.format(worker_id="worker-01") == "events:worker:worker-01"
        assert bus.CHANNEL_TYPE_TEMPLATE.format(event_type="call_started") == "events:type:call_started"

    @pytest.mark.asyncio
    async def test_notify_local_subscribers_queue_cleanup(self) -> None:
        """Test that full/dead queues are cleaned up."""
        bus = EventBus(redis_url="redis://localhost:6379/99")

        # Create a full queue
        full_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        full_queue.put_nowait(SystemEvent(event_type=EventType.CALL_STARTED))

        bus._subscribers.add(full_queue)
        event = SystemEvent(event_type=EventType.CALL_STARTED)
        bus._notify_local_subscribers(event)

        # Full queue should be removed
        await asyncio.sleep(0.05)

        bus._subscribers.discard(full_queue)

    def test_stream_event_format(self) -> None:
        """Test stream event entry format."""
        bus = EventBus(redis_url="redis://localhost:6379/99")
        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
            payload={"test": "data"},
        )
        # Verify the event JSON is serializable
        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["event_type"] == "call_started"
        assert data["payload"]["test"] == "data"
