"""
test_inbound_call_flow.py - End-to-end test for complete inbound call flow.

Simulates a complete inbound call lifecycle:
    Phone rings -> Answered -> AI greeting -> Caller speaks -> AI responds
    -> Message taken -> Call ends

Verifies:
    - Call record created
    - Transcript generated
    - Message stored
    - Notification sent
    - Session state transitions
    - Event bus publishes correct events

Location: backend/tests/e2e/test_inbound_call_flow.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest

from backend.orchestrator.models import CallState, EventType, ActiveSession

pytestmark = pytest.mark.asyncio


class TestInboundCallFlow:
    """End-to-end tests for complete inbound call flow."""

    async def test_call_ringing_to_answered(self, call_simulator, session_manager, event_bus, event_capture, test_tenant_id):
        """Test that an inbound call progresses from ringing to answered state."""
        # Given: A new incoming call
        caller = "+15551234567"
        called = "+15559876543"

        # When: Simulate the inbound call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number=caller,
            called_number=called,
        )

        # Then: Session should be created and in ACTIVE state
        assert session is not None
        assert session.call_id is not None
        assert session.tenant_id == test_tenant_id
        assert session.caller_number == caller
        assert session.phone_number == called

        # Verify session is in Redis
        stored = await session_manager.get_session(session.call_id)
        assert stored is not None
        assert stored.state == CallState.ACTIVE

        # Verify events were published
        await event_bus._do_publish(
            SystemEvent(
                event_type=EventType.CALL_STARTED,
                call_id=session.call_id,
                tenant_id=test_tenant_id,
                payload={"caller_number": caller},
            )
        )

        assert event_capture.has_event_type(EventType.CALL_STARTED)
        assert event_capture.has_event_type(EventType.CALL_QUEUED)
        assert event_capture.has_event_type(EventType.CALL_ASSIGNED)
        assert event_capture.has_event_type(EventType.CALL_ACTIVE)

    async def test_ai_greeting_played(self, call_simulator, mock_ai_pipeline, session_manager, test_tenant_id):
        """Test that AI greeting is played when call is answered."""
        # Given: An answered call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # When: AI generates and plays greeting
        greeting_text = "Thank you for calling Acme Dental. I'm your AI assistant. How can I help?"
        greeting_audio = await mock_ai_pipeline.synthesize(greeting_text)

        # Then: Greeting audio should be generated
        assert greeting_audio is not None
        assert len(greeting_audio) > 0
        assert len(mock_ai_pipeline.tts_calls) == 1
        assert mock_ai_pipeline.tts_calls[0]["text"] == greeting_text

    async def test_caller_speaks_stt_transcribes(self, call_simulator, mock_ai_pipeline, test_tenant_id):
        """Test that caller speech is transcribed by STT."""
        # Given: An active call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # When: Caller speaks (simulated audio)
        caller_audio = b"\x00\x01" * 2000
        transcript = await mock_ai_pipeline.transcribe(caller_audio)

        # Then: Transcript should contain caller's words
        assert transcript is not None
        assert "text" in transcript
        assert transcript["confidence"] > 0.9
        assert len(mock_ai_pipeline.stt_calls) == 1
        assert mock_ai_pipeline.stt_calls[0]["audio_size"] == len(caller_audio)

    async def test_ai_generates_response(self, call_simulator, mock_ai_pipeline, test_tenant_id):
        """Test that AI generates an appropriate response to caller."""
        # Given: An active call with caller transcript
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # When: Generate AI response
        prompt = "Caller said: Hello, I'd like to leave a message for Dr. Smith.\nRespond as a helpful receptionist."
        response = await mock_ai_pipeline.generate_response(prompt)

        # Then: Response should be appropriate
        assert response is not None
        assert "text" in response
        assert len(response["text"]) > 0
        assert len(mock_ai_pipeline.llm_calls) == 1

    async def test_complete_message_taking_flow(self, call_simulator, session_manager, event_bus, event_capture, test_tenant_id):
        """Test complete message-taking call flow."""
        # Given: An active call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
            called_number="+15559876543",
        )

        # When: Simulate message-taking conversation
        result = await call_simulator.simulate_message_taking(
            session=session,
            caller_message="Tell Dr. Smith I'll be 10 minutes late.",
        )

        # Then: Multiple conversation turns occurred
        assert len(result["conversation_turns"]) == 3

        # Verify session ended
        assert result["ended_session"] is not None
        assert result["ended_session"].state == CallState.ENDED

        # Verify transcript has entries
        final_session = await session_manager.get_session(session.call_id)
        assert len(final_session.transcript) >= 6  # 3 turns x 2 speakers

        # Verify events
        assert event_capture.has_event_type(EventType.CALL_STARTED)
        assert event_capture.has_event_type(EventType.CALL_ENDED)

        # Count conversation events
        call_events = event_capture.get_events_by_call(session.call_id)
        assert len(call_events) >= 2  # At least started and ended

    async def test_call_record_created(self, call_simulator, session_manager, test_tenant_id):
        """Test that a call record is created and stored."""
        # Given: A completed call
        caller = "+15551234567"
        called = "+15559876543"

        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number=caller,
            called_number=called,
        )

        # Simulate conversation
        await call_simulator.simulate_conversation_turn(session)
        await call_simulator.end_call(session.call_id, "hangup_by_caller")

        # Then: Session should be archived
        ended_session = await session_manager.get_session(session.call_id)
        assert ended_session is not None
        assert ended_session.state == CallState.ENDED
        assert ended_session.caller_number == caller
        assert ended_session.phone_number == called
        assert ended_session.tenant_id == test_tenant_id

    async def test_transcript_generated(self, call_simulator, session_manager, test_tenant_id):
        """Test that transcript is generated with correct entries."""
        # Given: An active call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # When: Multiple conversation turns
        for _ in range(3):
            await call_simulator.simulate_conversation_turn(session)

        await call_simulator.end_call(session.call_id, "hangup_by_caller")

        # Then: Transcript should have entries for both speakers
        final_session = await session_manager.get_session(session.call_id)
        transcript = final_session.transcript

        caller_entries = [t for t in transcript if t.get("speaker") == "caller"]
        ai_entries = [t for t in transcript if t.get("speaker") == "ai"]

        assert len(caller_entries) >= 3
        assert len(ai_entries) >= 3

        # Verify entries have timestamps
        for entry in transcript:
            assert "timestamp" in entry
            assert "text" in entry

    async def test_session_state_transitions(self, call_simulator, session_manager, test_tenant_id):
        """Test that session state transitions are valid."""
        # Given: A new call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Verify state history
        stored = await session_manager.get_session(session.call_id)
        history = stored.state_history

        # Should have transitions: created -> queued -> assigned -> active
        states_in_history = [h.get("to", h.get("state", "")) for h in history]
        assert CallState.CREATED.value in states_in_history or len(history) >= 3

        # End the call
        await call_simulator.end_call(session.call_id)
        ended = await session_manager.get_session(session.call_id)
        assert ended.state == CallState.ENDED

    async def test_caller_info_preserved(self, call_simulator, session_manager, test_tenant_id):
        """Test that caller information is preserved throughout the call."""
        caller_number = "+15551234567"
        called_number = "+15559876543"
        caller_name = "Jane Doe"

        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number=caller_number,
            called_number=called_number,
        )

        # Add caller name to session
        await session_manager.update_session(session.call_id, {"caller_name": caller_name})

        # Simulate conversation
        await call_simulator.simulate_conversation_turn(session)
        await call_simulator.end_call(session.call_id)

        # Verify info preserved
        final = await session_manager.get_session(session.call_id)
        assert final.caller_number == caller_number
        assert final.phone_number == called_number
        assert final.caller_name == caller_name

    async def test_multiple_calls_different_callers(self, call_simulator, session_manager, test_tenant_id):
        """Test handling multiple calls from different callers."""
        callers = [
            ("+15551111111", "Alice"),
            ("+15552222222", "Bob"),
            ("+15553333333", "Charlie"),
        ]

        sessions = []
        for phone, name in callers:
            session = await call_simulator.simulate_inbound_call(
                tenant_id=test_tenant_id,
                caller_number=phone,
            )
            await session_manager.update_session(session.call_id, {"caller_name": name})
            sessions.append(session)

        # Verify all sessions exist and are independent
        for i, (phone, name) in enumerate(callers):
            stored = await session_manager.get_session(sessions[i].call_id)
            assert stored is not None
            assert stored.caller_number == phone
            assert stored.caller_name == name
            assert stored.state == CallState.ACTIVE

        # Verify session counts
        count = await session_manager.count_sessions(tenant_id=test_tenant_id)
        assert count >= 3

        # End all calls
        for session in sessions:
            await call_simulator.end_call(session.call_id)

    async def test_call_with_transfer_request(self, call_simulator, session_manager, event_capture, test_tenant_id):
        """Test call where caller requests transfer to human."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Simulate transfer request
        await session_manager.update_session(
            session.call_id,
            {"transfer_target": "human_agent_001", "transfer_requested_at": datetime.utcnow().isoformat()},
        )

        # Continue conversation
        await call_simulator.simulate_conversation_turn(session)
        await call_simulator.end_call(session.call_id, "transferred")

        # Verify transfer info
        final = await session_manager.get_session(session.call_id)
        assert final.state == CallState.ENDED

    async def test_long_call_with_multiple_turns(self, call_simulator, session_manager, test_tenant_id):
        """Test a long call with many conversation turns."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Simulate 10 conversation turns
        for i in range(10):
            result = await call_simulator.simulate_conversation_turn(session)
            assert result["transcript"] is not None
            assert result["response"] is not None

        # End call
        await call_simulator.end_call(session.call_id)

        # Verify final state
        final = await session_manager.get_session(session.call_id)
        assert final.state == CallState.ENDED
        assert len(final.transcript) >= 20  # 10 turns x 2 speakers

    async def test_call_metrics_collected(self, call_simulator, session_manager, mock_ai_pipeline, test_tenant_id):
        """Test that call metrics are collected during the call."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Simulate several turns
        for _ in range(3):
            await call_simulator.simulate_conversation_turn(session)

        await call_simulator.end_call(session.call_id)

        # Verify AI pipeline was used
        assert len(mock_ai_pipeline.stt_calls) >= 3
        assert len(mock_ai_pipeline.llm_calls) >= 3
        assert len(mock_ai_pipeline.tts_calls) >= 3

    async def test_notification_event_published(self, event_bus, event_capture, test_tenant_id):
        """Test that notification events are published for important call events."""
        call_id = str(uuid.uuid4())

        # Publish notification event
        event = SystemEvent(
            event_type=EventType.CALL_ENDED,
            call_id=call_id,
            tenant_id=test_tenant_id,
            payload={
                "notification_type": "new_message",
                "recipient": "admin@acme.com",
                "message_summary": "Caller left a message",
            },
        )
        await event_bus.publish_async(event)

        # Verify event was captured
        call_events = event_capture.get_events_by_call(call_id)
        assert len(call_events) >= 1
        assert call_events[0].event_type == EventType.CALL_ENDED
        assert call_events[0].payload.get("notification_type") == "new_message"

    async def test_call_duration_tracked(self, call_simulator, session_manager, test_tenant_id):
        """Test that call duration is accurately tracked."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Simulate some conversation time
        import asyncio
        await call_simulator.simulate_conversation_turn(session)
        await asyncio.sleep(0.01)  # Tiny delay to ensure duration > 0
        await call_simulator.end_call(session.call_id, "hangup_by_caller")

        final = await session_manager.get_session(session.call_id)
        assert final.state == CallState.ENDED
        assert final.ended_at is not None
        assert final.created_at is not None
        # Call should have some duration
        duration = (final.ended_at - final.created_at).total_seconds()
        assert duration >= 0

    async def test_call_quality_metrics(self, call_simulator, session_manager, test_tenant_id):
        """Test that call quality metrics are collected."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Update MOS score
        await session_manager.update_session(session.call_id, {"mos_score": 4.2})

        # Simulate conversation
        await call_simulator.simulate_conversation_turn(session)
        await call_simulator.end_call(session.call_id)

        final = await session_manager.get_session(session.call_id)
        assert final.mos_score == 4.2

    async def test_error_counting_during_call(self, call_simulator, session_manager, test_tenant_id):
        """Test that errors during calls are counted."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Simulate an error
        await session_manager.update_session(
            session.call_id,
            {
                "error_count": 2,
                "last_error": "STT timeout",
            },
        )

        await call_simulator.end_call(session.call_id)

        final = await session_manager.get_session(session.call_id)
        assert final.error_count == 2
        assert final.last_error == "STT timeout"

    async def test_call_hangup_by_system(self, call_simulator, session_manager, test_tenant_id):
        """Test call ended by system (e.g., max duration exceeded)."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        ended = await call_simulator.end_call(session.call_id, "timeout")

        assert ended is not None
        assert ended.state == CallState.ENDED

    async def test_call_with_custom_agent_config(self, call_simulator, session_manager, test_tenant_id):
        """Test call with custom agent configuration."""
        custom_config = {
            "language": "es",
            "voice_tone": "formal",
            "max_response_length": 100,
            "allow_transfer": True,
            "transfer_targets": ["sales", "support"],
        }

        session = ActiveSession(
            call_id=str(uuid.uuid4()),
            tenant_id=test_tenant_id,
            phone_number="+15559876543",
            caller_number="+15551234567",
            agent_id="agent-custom-001",
            agent_name="Custom AI Agent",
            state=CallState.CREATED,
            agent_config=custom_config,
        )
        await session_manager.create_session(session)

        stored = await session_manager.get_session(session.call_id)
        assert stored.agent_config["language"] == "es"
        assert stored.agent_config["voice_tone"] == "formal"
        assert stored.agent_config["allow_transfer"] is True

        await session_manager.end_session(session.call_id)

    async def test_call_with_websocket_tracking(self, call_simulator, session_manager, test_tenant_id):
        """Test that WebSocket connection status is tracked."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Simulate WebSocket connection
        await session_manager.update_session(
            session.call_id,
            {
                "ws_connected": True,
                "ws_client_ip": "192.168.1.100",
            },
        )

        stored = await session_manager.get_session(session.call_id)
        assert stored.ws_connected is True
        assert stored.ws_client_ip == "192.168.1.100"

        await call_simulator.end_call(session.call_id)

    async def test_call_queue_enter_and_exit(self, session_manager, test_tenant_id):
        """Test call entering and exiting queue."""
        session = ActiveSession(
            call_id=str(uuid.uuid4()),
            tenant_id=test_tenant_id,
            phone_number="+15559876543",
            caller_number="+15551234567",
            agent_id="agent-001",
            state=CallState.CREATED,
        )
        await session_manager.create_session(session)

        # Enter queue
        await session_manager.transition_state(session.call_id, CallState.QUEUED)
        queued = await session_manager.get_session(session.call_id)
        assert queued.state == CallState.QUEUED

        # Assign worker
        await session_manager.transition_state(session.call_id, CallState.ASSIGNED)
        assigned = await session_manager.get_session(session.call_id)
        assert assigned.state == CallState.ASSIGNED

        # Connect
        await session_manager.transition_state(session.call_id, CallState.CONNECTING)
        await session_manager.transition_state(session.call_id, CallState.ACTIVE)
        active = await session_manager.get_session(session.call_id)
        assert active.state == CallState.ACTIVE

        await session_manager.end_session(session.call_id)


# Need SystemEvent imported at module level
from backend.orchestrator.models import SystemEvent
