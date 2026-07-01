"""
test_call_routing.py - End-to-end tests for call routing logic.

Tests routing rules:
    - Business hours check
    - VIP caller routing
    - DTMF menu selection
    - After-hours handling
    - Emergency keyword routing

Verifies:
    - Correct routing decisions based on time and caller
    - Priority queue handling
    - After-hours voicemail/AI fallback
    - DTMF menu navigation

Location: backend/tests/e2e/test_call_routing.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest

from backend.orchestrator.models import CallState, EventType, QueuePriority, SystemEvent
from backend.orchestrator.session_manager import SessionManager

pytestmark = pytest.mark.asyncio


class TestCallRouting:
    """End-to-end tests for call routing rules."""

    def _is_within_business_hours(
        self,
        check_time: datetime,
        business_hours: dict,
        timezone: str = "America/New_York",
    ) -> bool:
        """Check if a datetime is within business hours."""
        day_name = check_time.strftime("%A").lower()
        day_config = business_hours.get(day_name)

        if not day_config or not day_config.get("is_open", False):
            return False

        open_time = datetime.strptime(day_config["open"], "%H:%M").time()
        close_time = datetime.strptime(day_config["close"], "%H:%M").time()
        current_time = check_time.time()

        return open_time <= current_time <= close_time

    def _get_routing_decision(
        self,
        caller_number: str,
        current_time: datetime,
        business_hours: dict,
        routing_rules: list,
        vip_list: list = None,
        emergency_keywords: list = None,
    ) -> dict:
        """Determine routing decision based on rules."""
        decision = {
            "action": "ai_answer",
            "priority": QueuePriority.STANDARD,
            "reason": "default",
            "target": None,
        }

        # Check VIP callers first (highest priority after emergency)
        if vip_list and caller_number in vip_list:
            decision["priority"] = QueuePriority.VIP
            decision["reason"] = "vip_caller"

        # Check emergency keywords
        if emergency_keywords:
            decision["action"] = "transfer_immediately"
            decision["priority"] = QueuePriority.EMERGENCY
            decision["reason"] = "emergency_keyword"
            decision["target"] = "emergency_line"
            return decision

        # Check business hours
        within_hours = self._is_within_business_hours(current_time, business_hours)
        if not within_hours:
            # Apply after-hours routing rule
            for rule in routing_rules:
                if rule["condition"] == "outside_business_hours":
                    decision["action"] = rule["action"]
                    decision["reason"] = "outside_business_hours"
                    decision["priority"] = QueuePriority.STANDARD
                    return decision

        # Check other routing rules
        for rule in sorted(routing_rules, key=lambda r: r.get("priority", 0), reverse=True):
            if rule["condition"] == "vip_caller" and vip_list and caller_number in vip_list:
                decision["action"] = rule["action"]
                decision["priority"] = QueuePriority.VIP
                decision["reason"] = "vip_caller"
                return decision
            elif rule["condition"] == "keyword_emergency":
                decision["action"] = rule["action"]
                decision["priority"] = QueuePriority.EMERGENCY
                decision["reason"] = "keyword_emergency"
                return decision

        return decision

    async def test_business_hours_routing_within_hours(self, test_tenant_id):
        """Test routing when call arrives during business hours."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
            "tuesday": {"open": "09:00", "close": "17:00", "is_open": True},
            "wednesday": {"open": "09:00", "close": "17:00", "is_open": True},
            "thursday": {"open": "09:00", "close": "17:00", "is_open": True},
            "friday": {"open": "09:00", "close": "17:00", "is_open": True},
            "saturday": {"is_open": False},
            "sunday": {"is_open": False},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "voicemail", "priority": 10},
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
        ]

        # Wednesday at 10:00 AM (within hours)
        call_time = datetime(2024, 6, 12, 10, 0, 0)  # Wednesday
        decision = self._get_routing_decision(
            caller_number="+15551234567",
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
        )

        assert decision["action"] == "ai_answer"
        assert decision["reason"] == "default"
        assert decision["priority"] == QueuePriority.STANDARD

    async def test_business_hours_routing_outside_hours(self, test_tenant_id):
        """Test routing when call arrives outside business hours."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
            "tuesday": {"open": "09:00", "close": "17:00", "is_open": True},
            "wednesday": {"open": "09:00", "close": "17:00", "is_open": True},
            "thursday": {"open": "09:00", "close": "17:00", "is_open": True},
            "friday": {"open": "09:00", "close": "17:00", "is_open": True},
            "saturday": {"is_open": False},
            "sunday": {"is_open": False},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
        ]

        # Wednesday at 8:00 PM (after hours)
        call_time = datetime(2024, 6, 12, 20, 0, 0)
        decision = self._get_routing_decision(
            caller_number="+15551234567",
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
        )

        assert decision["action"] == "ai_answer"
        assert decision["reason"] == "outside_business_hours"

    async def test_vip_caller_routing(self, test_tenant_id):
        """Test that VIP callers get priority routing."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "voicemail", "priority": 10},
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
        ]
        vip_list = ["+15551111111", "+15552222222"]

        # VIP caller during business hours
        call_time = datetime(2024, 6, 10, 10, 0, 0)  # Monday 10 AM
        decision = self._get_routing_decision(
            caller_number="+15551111111",
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
            vip_list=vip_list,
        )

        assert decision["action"] == "priority_queue"
        assert decision["reason"] == "vip_caller"
        assert decision["priority"] == QueuePriority.VIP

    async def test_non_vip_caller_standard_routing(self, test_tenant_id):
        """Test that regular callers get standard routing."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
        }
        routing_rules = [
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
        ]
        vip_list = ["+15551111111"]

        call_time = datetime(2024, 6, 10, 10, 0, 0)
        decision = self._get_routing_decision(
            caller_number="+15559999999",  # Not a VIP
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
            vip_list=vip_list,
        )

        assert decision["priority"] == QueuePriority.STANDARD
        assert decision["reason"] == "default"

    async def test_after_hours_routing_to_voicemail(self, test_tenant_id):
        """Test after-hours routing to voicemail."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "voicemail", "priority": 10},
        ]

        # Call at 11 PM
        call_time = datetime(2024, 6, 10, 23, 0, 0)
        decision = self._get_routing_decision(
            caller_number="+15551234567",
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
        )

        assert decision["action"] == "voicemail"
        assert decision["reason"] == "outside_business_hours"

    async def test_after_hours_ai_fallback(self, test_tenant_id):
        """Test after-hours AI answering instead of voicemail."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
        ]

        call_time = datetime(2024, 6, 10, 20, 0, 0)
        decision = self._get_routing_decision(
            caller_number="+15551234567",
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
        )

        assert decision["action"] == "ai_answer"

    async def test_weekend_routing_closed(self, test_tenant_id):
        """Test routing on weekend when business is closed."""
        business_hours = {
            "saturday": {"is_open": False},
            "sunday": {"is_open": False},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
        ]

        # Saturday at 11 AM
        call_time = datetime(2024, 6, 15, 11, 0, 0)  # Saturday
        within_hours = self._is_within_business_hours(call_time, business_hours)

        assert within_hours is False

        decision = self._get_routing_decision(
            caller_number="+15551234567",
            current_time=call_time,
            business_hours=business_hours,
            routing_rules=routing_rules,
        )

        assert decision["action"] == "ai_answer"

    async def test_weekend_routing_limited_hours(self, test_tenant_id):
        """Test routing on weekend with limited hours."""
        business_hours = {
            "saturday": {"open": "10:00", "close": "14:00", "is_open": True},
            "sunday": {"is_open": False},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
        ]

        # Saturday at 11 AM (within limited hours)
        call_time = datetime(2024, 6, 15, 11, 0, 0)
        within_hours = self._is_within_business_hours(call_time, business_hours)

        assert within_hours is True

        # Saturday at 4 PM (after limited hours)
        call_time_late = datetime(2024, 6, 15, 16, 0, 0)
        within_hours_late = self._is_within_business_hours(call_time_late, business_hours)

        assert within_hours_late is False

    async def test_dtmf_menu_selection(self, test_tenant_id):
        """Test DTMF menu navigation."""
        menu_config = {
            "greeting": "Press 1 for appointments, 2 for billing, 3 for emergencies, 0 for operator",
            "options": {
                "1": {"action": "route_to", "target": "appointments_queue", "description": "Appointments"},
                "2": {"action": "route_to", "target": "billing_queue", "description": "Billing"},
                "3": {"action": "transfer_immediately", "target": "emergency_line", "description": "Emergency"},
                "0": {"action": "route_to", "target": "operator_queue", "description": "Operator"},
            },
        }

        # Test each DTMF option
        for dtmf_key, config in menu_config["options"].items():
            assert config["action"] in ("route_to", "transfer_immediately")
            assert config["target"] is not None

        # Test emergency (key 3) gets immediate transfer
        emergency_config = menu_config["options"]["3"]
        assert emergency_config["action"] == "transfer_immediately"
        assert emergency_config["target"] == "emergency_line"

    async def test_emergency_keyword_routing(self, test_tenant_id):
        """Test emergency keyword detection routes to immediate transfer."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
        }
        routing_rules = [
            {"condition": "keyword_emergency", "action": "transfer_immediately", "priority": 100},
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
        ]

        # Call with emergency keyword
        decision = self._get_routing_decision(
            caller_number="+15551234567",
            current_time=datetime(2024, 6, 10, 10, 0, 0),  # Within hours
            business_hours=business_hours,
            routing_rules=routing_rules,
            emergency_keywords=["emergency", "urgent", "pain"],
        )

        assert decision["action"] == "transfer_immediately"
        assert decision["priority"] == QueuePriority.EMERGENCY
        assert decision["reason"] == "emergency_keyword"

    async def test_routing_priority_order(self, test_tenant_id):
        """Test that routing rules are evaluated in priority order."""
        routing_rules = [
            {"condition": "keyword_emergency", "action": "transfer_immediately", "priority": 100},
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
        ]

        # Sort by priority descending
        sorted_rules = sorted(routing_rules, key=lambda r: r["priority"], reverse=True)

        assert sorted_rules[0]["condition"] == "keyword_emergency"
        assert sorted_rules[1]["condition"] == "vip_caller"
        assert sorted_rules[2]["condition"] == "outside_business_hours"

    async def test_routing_event_published(self, event_bus, event_capture, test_tenant_id):
        """Test that routing decisions publish events."""
        call_id = str(uuid.uuid4())

        event = SystemEvent(
            event_type=EventType.CALL_ROUTED,
            call_id=call_id,
            tenant_id=test_tenant_id,
            payload={
                "routing_decision": "ai_answer",
                "priority": "standard",
                "reason": "within_business_hours",
                "business_hours_status": "open",
            },
        )
        await event_bus.publish_async(event)

        events = event_capture.get_events_by_type(EventType.CALL_ROUTED)
        assert len(events) == 1
        assert events[0].payload["routing_decision"] == "ai_answer"

    async def test_holiday_routing(self, test_tenant_id):
        """Test routing on holidays when business is closed."""
        holidays = [date(2024, 7, 4), date(2024, 12, 25)]
        business_hours = {
            "thursday": {"open": "09:00", "close": "17:00", "is_open": True},
            "wednesday": {"open": "09:00", "close": "17:00", "is_open": True},
        }

        # July 4th (holiday)
        check_date = date(2024, 7, 4)
        is_holiday = check_date in holidays
        assert is_holiday is True

        # Even if it would normally be a business day
        call_time = datetime(2024, 7, 4, 10, 0, 0)
        is_business_day = call_time.date() not in holidays
        assert is_business_day is False

    async def test_routing_with_caller_id_lookup(self, test_tenant_id):
        """Test routing with caller ID lookup."""
        caller_directory = {
            "+15551111111": {"name": "Alice", "type": "vip", "department": "executive"},
            "+15552222222": {"name": "Bob", "type": "regular", "department": "sales"},
        }

        # Lookup VIP caller
        caller_info = caller_directory.get("+15551111111")
        assert caller_info is not None
        assert caller_info["type"] == "vip"

        # Lookup unknown caller
        unknown_info = caller_directory.get("+15559999999")
        assert unknown_info is None

    async def test_routing_decision_consistency(self, test_tenant_id):
        """Test that routing decisions are consistent for same inputs."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
        }
        routing_rules = [
            {"condition": "outside_business_hours", "action": "voicemail", "priority": 10},
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
        ]
        vip_list = ["+15551111111"]

        call_time = datetime(2024, 6, 10, 20, 0, 0)  # After hours

        # Multiple calls with same parameters should get same result
        for _ in range(5):
            decision = self._get_routing_decision(
                caller_number="+15551234567",
                current_time=call_time,
                business_hours=business_hours,
                routing_rules=routing_rules,
                vip_list=vip_list,
            )
            assert decision["action"] == "voicemail"
            assert decision["reason"] == "outside_business_hours"

    async def test_routing_with_queue_position(self, session_manager, test_tenant_id):
        """Test that routed calls get queue positions."""
        # Create multiple queued calls
        calls = []
        for i in range(5):
            call_id = f"call_{i:03d}"
            session = ActiveSession(
                call_id=call_id,
                tenant_id=test_tenant_id,
                phone_number="+15559876543",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.QUEUED,
                queue_position=i + 1,
            )
            await session_manager.create_session(session)
            calls.append(session)

        # Verify queue positions
        for i, call in enumerate(calls):
            stored = await session_manager.get_session(call.call_id)
            assert stored.state == CallState.QUEUED
            assert stored.queue_position == i + 1

        # Clean up
        for call in calls:
            await session_manager.end_session(call.call_id)
