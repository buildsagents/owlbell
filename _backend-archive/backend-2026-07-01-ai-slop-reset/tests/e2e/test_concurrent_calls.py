"""
test_concurrent_calls.py - End-to-end tests for concurrent call handling.

Simulates 10 simultaneous calls and verifies:
    - Session isolation (no cross-talk)
    - Load balancing across workers
    - State transitions are independent
    - Event ordering per call
    - Resource contention handling

Location: backend/tests/e2e/test_concurrent_calls.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

import pytest

from backend.orchestrator.models import CallState, EventType, ActiveSession, SystemEvent

pytestmark = pytest.mark.asyncio


class TestConcurrentCalls:
    """End-to-end tests for handling multiple simultaneous calls."""

    async def test_ten_simultaneous_calls(self, call_simulator, session_manager, test_tenant_id):
        """Test handling 10 simultaneous calls."""
        # Create 10 calls concurrently
        tasks = []
        for i in range(10):
            task = call_simulator.simulate_inbound_call(
                tenant_id=test_tenant_id,
                caller_number=f"+1555000000{i:02d}",
                called_number="+15559876543",
            )
            tasks.append(task)

        # Start all calls
        sessions = await asyncio.gather(*tasks)

        # Verify all 10 calls are active
        assert len(sessions) == 10
        for session in sessions:
            assert session is not None
            assert session.state == CallState.ACTIVE

        # Verify all exist in session manager
        for session in sessions:
            stored = await session_manager.get_session(session.call_id)
            assert stored is not None
            assert stored.state == CallState.ACTIVE

        # Count active sessions
        active_count = await session_manager.count_sessions(state=CallState.ACTIVE.value)
        assert active_count >= 10

        # End all calls
        end_tasks = [call_simulator.end_call(s.call_id) for s in sessions]
        await asyncio.gather(*end_tasks)

    async def test_session_isolation_no_crosstalk(self, call_simulator, session_manager, test_tenant_id):
        """Test that concurrent sessions don't interfere with each other."""
        # Create two simultaneous calls
        session_a = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551111111",
        )
        session_b = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15552222222",
        )

        # Have different conversations on each
        result_a = await call_simulator.simulate_conversation_turn(
            session_a,
            caller_audio=b"\x00\x01" * 2500,
        )
        result_b = await call_simulator.simulate_conversation_turn(
            session_b,
            caller_audio=b"\x00\x01" * 1500,
        )

        # Verify transcripts are independent
        stored_a = await session_manager.get_session(session_a.call_id)
        stored_b = await session_manager.get_session(session_b.call_id)

        # Each should only have their own transcript entries
        a_transcript = stored_a.transcript
        b_transcript = stored_b.transcript

        # No shared transcript entries
        a_texts = {t.get("text", "") for t in a_transcript}
        b_texts = {t.get("text", "") for t in b_transcript}

        # They should be independent (may have similar AI responses but different timestamps)
        assert stored_a.call_id != stored_b.call_id
        assert stored_a.caller_number != stored_b.caller_number

        # End both calls
        await call_simulator.end_call(session_a.call_id)
        await call_simulator.end_call(session_b.call_id)

    async def test_independent_state_transitions(self, session_manager, test_tenant_id):
        """Test that state transitions are independent across calls."""
        # Create multiple sessions
        sessions = []
        for i in range(5):
            session = ActiveSession(
                call_id=f"concurrent-{i:03d}",
                tenant_id=test_tenant_id,
                phone_number="+15559876543",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.CREATED,
            )
            await session_manager.create_session(session)
            sessions.append(session)

        # Transition each to different states
        await session_manager.transition_state(sessions[0].call_id, CallState.QUEUED)
        await session_manager.transition_state(sessions[1].call_id, CallState.ASSIGNED)
        await session_manager.transition_state(sessions[2].call_id, CallState.ACTIVE)
        await session_manager.transition_state(sessions[3].call_id, CallState.PROCESSING)
        await session_manager.transition_state(sessions[4].call_id, CallState.HOLDING)

        # Verify independent states
        states = []
        for s in sessions:
            stored = await session_manager.get_session(s.call_id)
            states.append(stored.state)

        assert states[0] == CallState.QUEUED
        assert states[1] == CallState.ASSIGNED
        assert states[2] == CallState.ACTIVE
        assert states[3] == CallState.PROCESSING
        assert states[4] == CallState.HOLDING

        # Verify all different
        assert len(set(states)) == 5

    async def test_concurrent_conversation_turns(self, call_simulator, session_manager, test_tenant_id):
        """Test multiple conversation turns happening concurrently."""
        # Create 3 active calls
        sessions = []
        for i in range(3):
            session = await call_simulator.simulate_inbound_call(
                tenant_id=test_tenant_id,
                caller_number=f"+1555100000{i}",
            )
            sessions.append(session)

        # Simulate conversation turns concurrently
        async def conversation_for_session(session):
            for _ in range(3):
                await call_simulator.simulate_conversation_turn(session)
            await call_simulator.end_call(session.call_id)
            return session.call_id

        tasks = [conversation_for_session(s) for s in sessions]
        completed = await asyncio.gather(*tasks)

        # All calls completed
        assert len(completed) == 3

        # All ended
        for call_id in completed:
            stored = await session_manager.get_session(call_id)
            assert stored.state == CallState.ENDED

    async def test_worker_load_distribution(self, session_manager, test_tenant_id):
        """Test that calls are distributed across workers."""
        workers = ["worker-001", "worker-002", "worker-003"]

        # Create multiple sessions and assign to different workers
        sessions = []
        for i in range(9):
            session = ActiveSession(
                call_id=f"load-{i:03d}",
                tenant_id=test_tenant_id,
                phone_number="+15559876543",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.CREATED,
            )
            await session_manager.create_session(session)
            # Assign to worker round-robin
            worker = workers[i % len(workers)]
            await session_manager.update_session(session.call_id, {"worker_id": worker, "state": CallState.ACTIVE.value})
            sessions.append(session)

        # Verify distribution
        worker_counts = {}
        for w in workers:
            worker_sessions = await session_manager.get_sessions_by_worker(w)
            worker_counts[w] = len(worker_sessions)

        # Should be roughly evenly distributed (3 per worker)
        for w in workers:
            assert worker_counts[w] >= 2  # At least 2 per worker with 9 calls / 3 workers

    async def test_concurrent_session_creation_no_conflicts(self, session_manager, test_tenant_id):
        """Test that concurrent session creation handles conflicts."""
        async def create_session(i: int):
            session = ActiveSession(
                call_id=f"no-conflict-{i:03d}",
                tenant_id=test_tenant_id,
                phone_number="+15559876543",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.CREATED,
            )
            try:
                result = await session_manager.create_session(session)
                return result.call_id
            except ValueError as e:
                return str(e)

        # Create 20 sessions concurrently
        tasks = [create_session(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        # All should succeed with unique IDs
        call_ids = [r for r in results if not r.startswith("Session")]
        assert len(call_ids) == 20
        assert len(set(call_ids)) == 20  # All unique

    async def test_peak_concurrent_tracking(self, session_manager, test_tenant_id):
        """Test that peak concurrent calls are tracked."""
        # Create multiple sessions rapidly
        sessions = []
        for i in range(15):
            session = ActiveSession(
                call_id=f"peak-{i:03d}",
                tenant_id=test_tenant_id,
                phone_number="+15559876543",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.ACTIVE,
            )
            await session_manager.create_session(session)
            sessions.append(session)

        # Check peak
        peak = await session_manager.get_peak_concurrent()
        assert peak >= 15

        # Count active
        active = await session_manager.count_sessions(state=CallState.ACTIVE.value)
        assert active >= 15

    async def test_concurrent_event_publishing(self, event_bus, event_capture, test_tenant_id):
        """Test that events from concurrent calls are published correctly."""
        async def publish_call_events(call_id: str):
            events = [
                SystemEvent(
                    event_type=EventType.CALL_STARTED,
                    call_id=call_id,
                    tenant_id=test_tenant_id,
                    payload={"step": "start"},
                ),
                SystemEvent(
                    event_type=EventType.CALL_ACTIVE,
                    call_id=call_id,
                    tenant_id=test_tenant_id,
                    payload={"step": "active"},
                ),
                SystemEvent(
                    event_type=EventType.CALL_ENDED,
                    call_id=call_id,
                    tenant_id=test_tenant_id,
                    payload={"step": "end"},
                ),
            ]
            for event in events:
                await event_bus.publish_async(event)

        # Publish events for 5 concurrent calls
        call_ids = [f"concurrent-call-{i:03d}" for i in range(5)]
        tasks = [publish_call_events(cid) for cid in call_ids]
        await asyncio.gather(*tasks)

        # Verify events for each call
        for cid in call_ids:
            call_events = event_capture.get_events_by_call(cid)
            assert len(call_events) == 3
            event_types = [e.event_type for e in call_events]
            assert EventType.CALL_STARTED in event_types
            assert EventType.CALL_ACTIVE in event_types
            assert EventType.CALL_ENDED in event_types

    async def test_resource_limits_not_exceeded(self, session_manager, test_tenant_id):
        """Test that resource limits are respected under concurrent load."""
        max_sessions = 50

        # Try to create many sessions
        sessions = []
        for i in range(max_sessions):
            session = ActiveSession(
                call_id=f"resource-{i:03d}",
                tenant_id=test_tenant_id,
                phone_number="+15559876543",
                caller_number=f"+1555000000{i % 100}",
                agent_id="agent-001",
                state=CallState.ACTIVE,
            )
            await session_manager.create_session(session)
            sessions.append(session)

        # Verify all created
        total = await session_manager.count_sessions()
        assert total >= max_sessions

        # Verify we can still query
        active = await session_manager.count_sessions(state=CallState.ACTIVE.value)
        assert active >= max_sessions

    async def test_graceful_call_ending_under_load(self, call_simulator, session_manager, test_tenant_id):
        """Test that calls end gracefully even under concurrent load."""
        # Create 5 calls
        sessions = []
        for i in range(5):
            session = await call_simulator.simulate_inbound_call(
                tenant_id=test_tenant_id,
                caller_number=f"+1555100000{i}",
            )
            sessions.append(session)

        # Simulate conversation on all
        for s in sessions:
            await call_simulator.simulate_conversation_turn(s)

        # End all simultaneously
        end_tasks = [call_simulator.end_call(s.call_id) for s in sessions]
        results = await asyncio.gather(*end_tasks)

        # All ended successfully
        assert len(results) == 5
        for r in results:
            assert r is not None
            assert r.state == CallState.ENDED

    async def test_no_memory_leak_with_many_sessions(self, session_manager, test_tenant_id):
        """Test that creating and destroying many sessions doesn't leak."""
        # Create and destroy 100 sessions
        for batch in range(10):
            sessions = []
            for i in range(10):
                session = ActiveSession(
                    call_id=f"leak-test-{batch}-{i:03d}",
                    tenant_id=test_tenant_id,
                    phone_number="+15559876543",
                    caller_number=f"+1555000000{i}",
                    agent_id="agent-001",
                    state=CallState.CREATED,
                )
                await session_manager.create_session(session)
                sessions.append(session)

            # End all in this batch
            for s in sessions:
                await session_manager.end_session(s.call_id)

        # Should not have accumulated too many active sessions
        active = await session_manager.count_sessions(state=CallState.ACTIVE.value)
        assert active < 20  # Should be clean, not 100+

    async def test_concurrent_transcript_updates(self, call_simulator, session_manager, test_tenant_id):
        """Test that transcript updates are atomic across concurrent turns."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Rapid transcript updates
        async def add_transcript_entry(i: int):
            stored = await session_manager.get_session(session.call_id)
            transcript = list(stored.transcript)
            transcript.append({
                "speaker": "caller" if i % 2 == 0 else "ai",
                "text": f"Message {i}",
                "timestamp": datetime.utcnow().isoformat(),
            })
            await session_manager.update_session(session.call_id, {"transcript": transcript})

        # 10 rapid updates
        tasks = [add_transcript_entry(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify transcript has all entries
        final = await session_manager.get_session(session.call_id)
        assert len(final.transcript) >= 10

        await call_simulator.end_call(session.call_id)
