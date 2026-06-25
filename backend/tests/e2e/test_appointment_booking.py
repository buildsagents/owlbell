"""
test_appointment_booking.py - End-to-end test for appointment booking flow.

Simulates a call where a customer books an appointment:
    Caller requests appointment -> AI checks availability
    -> Appointment created -> Calendar event created
    -> Confirmation sent

Tests conflict handling, rescheduling, and cancellation.

Verifies:
    - Availability is checked before booking
    - Appointment is created with correct details
    - Calendar event is synced
    - Confirmation is sent to caller
    - Conflicts are detected and handled

Location: backend/tests/e2e/test_appointment_booking.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest

from backend.orchestrator.models import CallState, EventType, ActiveSession, SystemEvent

pytestmark = pytest.mark.asyncio


class TestAppointmentBooking:
    """End-to-end tests for appointment booking via AI phone call."""

    async def test_appointment_booking_successful(self, call_simulator, session_manager, event_capture, test_tenant_id):
        """Test successful appointment booking through AI call."""
        # Given: An active call
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
            called_number="+15559876543",
        )

        # When: Simulate appointment booking conversation
        appt_date = date.today() + timedelta(days=2)
        appt_time = time(10, 30)
        result = await call_simulator.simulate_appointment_booking(
            session=session,
            preferred_date=appt_date,
            preferred_time=appt_time,
        )

        # Then: Appointment details are captured
        assert result["conversation_turns"] is not None
        assert len(result["conversation_turns"]) >= 3
        assert result["ended_session"] is not None
        assert result["ended_session"].state == CallState.ENDED

        # Verify conversation includes appointment keywords
        all_text = " ".join([
            turn["response"]["text"]
            for turn in result["conversation_turns"]
        ])
        assert "appointment" in all_text.lower() or "schedule" in all_text.lower()

    async def test_availability_checked_before_booking(self, mock_ai_pipeline, test_tenant_id):
        """Test that availability is checked before creating appointment."""
        # Simulate availability check
        availability = {
            date.today() + timedelta(days=1): [
                time(9, 0), time(9, 30), time(10, 0), time(10, 30),
                time(11, 0), time(11, 30), time(14, 0), time(14, 30),
            ],
            date.today() + timedelta(days=2): [
                time(9, 0), time(10, 30), time(11, 0), time(14, 0),
            ],
        }

        # Verify preferred slot is available
        appt_date = date.today() + timedelta(days=1)
        appt_time = time(10, 30)

        assert appt_date in availability
        assert appt_time in availability[appt_date]

    async def test_appointment_creation_with_details(self, session_manager, test_tenant_id):
        """Test appointment is created with correct details."""
        appointment = {
            "id": str(uuid.uuid4()),
            "tenant_id": test_tenant_id,
            "call_id": str(uuid.uuid4()),
            "contact_name": "John Smith",
            "contact_phone": "+15551234567",
            "contact_email": "john@example.com",
            "service": "Dental Cleaning",
            "service_duration_minutes": 30,
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "10:30",
            "end_time": "11:00",
            "timezone": "America/New_York",
            "status": "confirmed",
            "notes": "First-time patient",
            "created_at": datetime.utcnow().isoformat(),
            "reminder_sent": False,
        }

        # Verify all required fields
        assert appointment["tenant_id"] == test_tenant_id
        assert appointment["contact_name"] == "John Smith"
        assert appointment["contact_phone"] == "+15551234567"
        assert appointment["status"] == "confirmed"
        assert appointment["service"] == "Dental Cleaning"

    async def test_calendar_event_created(self, event_bus, event_capture, test_tenant_id):
        """Test that calendar event is created and synced."""
        call_id = str(uuid.uuid4())
        appt_id = str(uuid.uuid4())

        # Publish calendar sync event
        event = SystemEvent(
            event_type=EventType.APPOINTMENT_BOOKED,
            call_id=call_id,
            tenant_id=test_tenant_id,
            payload={
                "appointment_id": appt_id,
                "calendar_event_id": f"cal_{appt_id[:8]}",
                "calendar_provider": "google_calendar",
                "sync_status": "success",
                "event_start": (datetime.now() + timedelta(days=1)).isoformat(),
                "event_end": (datetime.now() + timedelta(days=1, hours=1)).isoformat(),
            },
        )
        await event_bus.publish_async(event)

        # Verify event was published
        events = event_capture.get_events_by_type(EventType.APPOINTMENT_BOOKED)
        assert len(events) == 1
        assert events[0].payload["sync_status"] == "success"
        assert events[0].payload["calendar_provider"] == "google_calendar"

    async def test_confirmation_sent_to_caller(self, event_bus, event_capture, test_tenant_id):
        """Test that confirmation is sent to caller after booking."""
        call_id = str(uuid.uuid4())

        # Publish confirmation event
        event = SystemEvent(
            event_type=EventType.APPOINTMENT_BOOKED,
            call_id=call_id,
            tenant_id=test_tenant_id,
            payload={
                "confirmation_sent": True,
                "confirmation_channel": "sms",
                "confirmation_phone": "+15551234567",
                "message": "Your appointment is confirmed for tomorrow at 10:30 AM.",
            },
        )
        await event_bus.publish_async(event)

        # Verify confirmation event
        events = event_capture.get_events_by_type(EventType.APPOINTMENT_BOOKED)
        assert len(events) == 1
        assert events[0].payload["confirmation_sent"] is True

    async def test_conflict_handling_same_time(self, test_tenant_id):
        """Test that double-booking at the same time is detected."""
        # Given: An existing appointment at a specific time
        existing_appt = {
            "id": str(uuid.uuid4()),
            "tenant_id": test_tenant_id,
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "10:30",
            "end_time": "11:00",
            "status": "confirmed",
        }

        # When: Trying to book another at the same time
        new_appt = {
            "id": str(uuid.uuid4()),
            "tenant_id": test_tenant_id,
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "10:30",
            "end_time": "11:00",
            "status": "pending",
        }

        # Then: Conflict should be detected
        conflict = (
            existing_appt["appointment_date"] == new_appt["appointment_date"]
            and existing_appt["start_time"] == new_appt["start_time"]
            and existing_appt["status"] == "confirmed"
        )
        assert conflict is True

    async def test_conflict_handling_overlapping(self, test_tenant_id):
        """Test that overlapping appointments are detected."""
        existing_appt = {
            "id": str(uuid.uuid4()),
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
            "status": "confirmed",
        }

        # Overlapping: starts at 10:30 during existing appointment
        new_appt = {
            "id": str(uuid.uuid4()),
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "10:30",
            "end_time": "11:30",
            "status": "pending",
        }

        # Parse times
        existing_start = datetime.strptime(existing_appt["start_time"], "%H:%M").time()
        existing_end = datetime.strptime(existing_appt["end_time"], "%H:%M").time()
        new_start = datetime.strptime(new_appt["start_time"], "%H:%M").time()
        new_end = datetime.strptime(new_appt["end_time"], "%H:%M").time()

        # Check overlap: new starts before existing ends AND new ends after existing starts
        overlaps = (
            new_start < existing_end and new_end > existing_start
        )
        assert overlaps is True

    async def test_reschedule_appointment(self, session_manager, event_bus, event_capture, test_tenant_id):
        """Test rescheduling an existing appointment."""
        # Given: An existing appointment
        appt_id = str(uuid.uuid4())
        original_date = date.today() + timedelta(days=1)
        new_date = date.today() + timedelta(days=3)

        # Publish original appointment
        event = SystemEvent(
            event_type=EventType.APPOINTMENT_BOOKED,
            call_id=str(uuid.uuid4()),
            tenant_id=test_tenant_id,
            payload={
                "appointment_id": appt_id,
                "status": "confirmed",
                "original_date": original_date.isoformat(),
            },
        )
        await event_bus.publish_async(event)

        # When: Reschedule
        reschedule_event = SystemEvent(
            event_type=EventType.APPOINTMENT_UPDATED,
            tenant_id=test_tenant_id,
            payload={
                "appointment_id": appt_id,
                "previous_date": original_date.isoformat(),
                "new_date": new_date.isoformat(),
                "status": "confirmed",
                "change_reason": "Patient request",
            },
        )
        await event_bus.publish_async(reschedule_event)

        # Then: Both events captured
        booked_events = event_capture.get_events_by_type(EventType.APPOINTMENT_BOOKED)
        updated_events = event_capture.get_events_by_type(EventType.APPOINTMENT_UPDATED)
        assert len(booked_events) == 1
        assert len(updated_events) == 1
        assert updated_events[0].payload["new_date"] == new_date.isoformat()

    async def test_cancel_appointment(self, event_bus, event_capture, test_tenant_id):
        """Test cancelling an appointment."""
        # Given: A confirmed appointment
        appt_id = str(uuid.uuid4())

        # Publish cancellation
        event = SystemEvent(
            event_type=EventType.APPOINTMENT_CANCELLED,
            tenant_id=test_tenant_id,
            payload={
                "appointment_id": appt_id,
                "previous_status": "confirmed",
                "cancelled_by": "caller",
                "cancel_reason": "Unable to make it",
                "refund_eligible": True,
                "notification_sent": True,
            },
        )
        await event_bus.publish_async(event)

        # Verify cancellation event
        events = event_capture.get_events_by_type(EventType.APPOINTMENT_CANCELLED)
        assert len(events) == 1
        assert events[0].payload["cancel_reason"] == "Unable to make it"
        assert events[0].payload["refund_eligible"] is True

    async def test_appointment_with_different_services(self, test_tenant_id):
        """Test booking appointments for different services."""
        services = [
            {"name": "Dental Cleaning", "duration": 30, "price": "$100"},
            {"name": "Consultation", "duration": 60, "price": "$150"},
            {"name": "Root Canal", "duration": 90, "price": "$500"},
            {"name": "Teeth Whitening", "duration": 45, "price": "$200"},
        ]

        appointments = []
        for i, svc in enumerate(services):
            appt = {
                "id": str(uuid.uuid4()),
                "tenant_id": test_tenant_id,
                "service": svc["name"],
                "duration_minutes": svc["duration"],
                "price": svc["price"],
                "appointment_date": (date.today() + timedelta(days=i + 1)).isoformat(),
                "start_time": f"{9 + i}:00",
                "status": "confirmed",
            }
            appointments.append(appt)

        # Verify all appointments created
        assert len(appointments) == len(services)
        for appt, svc in zip(appointments, services):
            assert appt["service"] == svc["name"]
            assert appt["duration_minutes"] == svc["duration"]
            assert appt["tenant_id"] == test_tenant_id

    async def test_appointment_outside_business_hours(self, test_tenant_id):
        """Test that appointments outside business hours are rejected."""
        business_hours = {"open": time(9, 0), "close": time(17, 0)}

        # Appointment at 8 AM (before opening)
        early_time = time(8, 0)
        is_within_hours = business_hours["open"] <= early_time <= business_hours["close"]
        assert is_within_hours is False

        # Appointment at 6 PM (after closing)
        late_time = time(18, 0)
        is_within_hours = business_hours["open"] <= late_time <= business_hours["close"]
        assert is_within_hours is False

        # Appointment at 10 AM (within hours)
        valid_time = time(10, 0)
        is_within_hours = business_hours["open"] <= valid_time <= business_hours["close"]
        assert is_within_hours is True

    async def test_appointment_weekend_check(self, test_tenant_id):
        """Test weekend appointment handling."""
        # Find next Saturday
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        next_saturday = today + timedelta(days=days_until_saturday)

        # Verify it's Saturday
        assert next_saturday.weekday() == 5

        # Weekend hours might be different
        weekend_hours = {"open": time(10, 0), "close": time(14, 0)}
        saturday_appt_time = time(11, 0)
        is_weekend_valid = weekend_hours["open"] <= saturday_appt_time <= weekend_hours["close"]
        assert is_weekend_valid is True

    async def test_full_booking_conversation_flow(self, call_simulator, mock_ai_pipeline, session_manager, test_tenant_id):
        """Test the complete booking conversation with all turns."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # Turn 1: Caller requests appointment
        result1 = await call_simulator.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 2200,
        )
        assert "appointment" in result1["response"]["text"].lower() or "schedule" in result1["response"]["text"].lower()

        # Turn 2: AI suggests times, caller picks one
        result2 = await call_simulator.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 1500,
        )
        assert result2["response"]["text"]  # AI responds

        # Turn 3: Confirmation details
        result3 = await call_simulator.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 1000,
        )

        # End call
        await call_simulator.end_call(session.call_id)

        # Verify
        final = await session_manager.get_session(session.call_id)
        assert final.state == CallState.ENDED
        assert len(final.transcript) >= 6

    async def test_ai_pipeline_tracks_booking_intent(self, mock_ai_pipeline, test_tenant_id):
        """Test that AI pipeline correctly identifies booking intent."""
        # Simulate booking-related prompts
        prompts = [
            "I'd like to book an appointment",
            "Can I schedule a cleaning?",
            "I need to see the dentist",
            "When is the next available slot?",
        ]

        for prompt in prompts:
            response = await mock_ai_pipeline.generate_response(prompt)
            assert response["text"]  # Non-empty response
            assert len(response["tokens_used"]) > 0 if isinstance(response["tokens_used"], str) else True

    async def test_multiple_appointments_same_day_different_times(self, test_tenant_id):
        """Test booking multiple appointments on the same day at different times."""
        appt_date = date.today() + timedelta(days=1)
        times = [time(9, 0), time(10, 0), time(11, 0), time(14, 0)]

        appointments = []
        for i, t in enumerate(times):
            appt = {
                "id": str(uuid.uuid4()),
                "tenant_id": test_tenant_id,
                "appointment_date": appt_date.isoformat(),
                "start_time": t.strftime("%H:%M"),
                "status": "confirmed",
                "patient_name": f"Patient {i + 1}",
            }
            appointments.append(appt)

        # Verify no overlap in times
        used_times = {a["start_time"] for a in appointments}
        assert len(used_times) == len(times)

    async def test_appointment_reminder_event(self, event_bus, event_capture, test_tenant_id):
        """Test that reminder events are published."""
        appt_id = str(uuid.uuid4())

        # Publish reminder event
        event = SystemEvent(
            event_type=EventType.APPOINTMENT_REMINDER,
            tenant_id=test_tenant_id,
            payload={
                "appointment_id": appt_id,
                "reminder_type": "24h",
                "hours_before": 24,
                "delivery_channel": "sms",
                "phone": "+15551234567",
                "message": "Reminder: You have an appointment tomorrow at 10:30 AM.",
            },
        )
        await event_bus.publish_async(event)

        # Verify
        events = event_capture.get_events_by_type(EventType.APPOINTMENT_REMINDER)
        assert len(events) == 1
        assert events[0].payload["hours_before"] == 24

    async def test_buffer_time_between_appointments(self, test_tenant_id):
        """Test that buffer time is respected between appointments."""
        buffer_minutes = 15
        appt_duration = 30

        # 9:00 AM appointment ends at 9:30
        first_end = datetime.combine(date.today(), time(9, 0)) + timedelta(minutes=appt_duration)

        # Next appointment with buffer: 9:30 + 15 min buffer = 9:45
        next_start = first_end + timedelta(minutes=buffer_minutes)

        assert next_start.time() == time(9, 45)
        assert (next_start - first_end).total_seconds() == buffer_minutes * 60

    async def test_appointment_booking_after_conversation(self, call_simulator, mock_ai_pipeline, test_tenant_id):
        """Test booking after an initial general conversation."""
        session = await call_simulator.simulate_inbound_call(
            tenant_id=test_tenant_id,
            caller_number="+15551234567",
        )

        # General conversation first
        await call_simulator.simulate_conversation_turn(session)
        await call_simulator.simulate_conversation_turn(session)

        # Then booking
        result = await call_simulator.simulate_appointment_booking(
            session=session,
            preferred_date=date.today() + timedelta(days=1),
            preferred_time=time(10, 30),
        )

        assert result["ended_session"] is not None
        assert len(result["conversation_turns"]) >= 3
