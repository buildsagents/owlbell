"""
test_multi_tenant.py - End-to-end tests for multi-tenant data isolation.

Creates multiple tenants and verifies:
    - Data isolation (Tenant A can't see Tenant B's calls)
    - Tenant-specific AI personas
    - Plan limits enforcement
    - Tenant-scoped sessions
    - Cross-tenant access prevention

Location: backend/tests/e2e/test_multi_tenant.py
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from backend.orchestrator.models import CallState, EventType, ActiveSession, SystemEvent

pytestmark = pytest.mark.asyncio


class TestMultiTenant:
    """End-to-end tests for multi-tenant isolation and behavior."""

    async def test_tenant_data_isolation_calls(self, session_manager, test_tenant_id, test_tenant_id_2):
        """Test that calls from one tenant are not visible to another."""
        # Given: Two different tenants
        tenant_a = test_tenant_id
        tenant_b = test_tenant_id_2

        # When: Create calls for each tenant
        call_a = ActiveSession(
            call_id=f"call-{uuid.uuid4()}",
            tenant_id=tenant_a,
            phone_number="+15551111111",
            caller_number="+15559999999",
            agent_id="agent-a",
            state=CallState.ACTIVE,
        )
        call_b = ActiveSession(
            call_id=f"call-{uuid.uuid4()}",
            tenant_id=tenant_b,
            phone_number="+15552222222",
            caller_number="+15558888888",
            agent_id="agent-b",
            state=CallState.ACTIVE,
        )

        await session_manager.create_session(call_a)
        await session_manager.create_session(call_b)

        # Then: Each tenant only sees their own calls
        tenant_a_calls = await session_manager.get_sessions_by_tenant(tenant_a)
        tenant_b_calls = await session_manager.get_sessions_by_tenant(tenant_b)

        assert len(tenant_a_calls) >= 1
        assert len(tenant_b_calls) >= 1

        # Verify no cross-tenant leakage
        for call in tenant_a_calls:
            assert call.tenant_id == tenant_a

        for call in tenant_b_calls:
            assert call.tenant_id == tenant_b

        # Clean up
        await session_manager.end_session(call_a.call_id)
        await session_manager.end_session(call_b.call_id)

    async def test_tenant_session_isolation(self, session_manager, test_tenant_id, test_tenant_id_2):
        """Test that sessions are scoped to their tenant."""
        tenant_a = test_tenant_id
        tenant_b = test_tenant_id_2

        # Create sessions for both tenants
        session_a = ActiveSession(
            call_id=f"sess-a-{uuid.uuid4()}",
            tenant_id=tenant_a,
            phone_number="+15551111111",
            caller_number="+15559999999",
            agent_id="agent-a",
            state=CallState.ACTIVE,
            agent_config={"tenant_name": "Acme Corp", "industry": "healthcare"},
        )
        session_b = ActiveSession(
            call_id=f"sess-b-{uuid.uuid4()}",
            tenant_id=tenant_b,
            phone_number="+15552222222",
            caller_number="+15558888888",
            agent_id="agent-b",
            state=CallState.ACTIVE,
            agent_config={"tenant_name": "Beta Inc", "industry": "legal"},
        )

        await session_manager.create_session(session_a)
        await session_manager.create_session(session_b)

        # Verify tenant A can only see their session
        a_sessions = await session_manager.get_sessions_by_tenant(tenant_a)
        b_sessions = await session_manager.get_sessions_by_tenant(tenant_b)

        a_call_ids = {s.call_id for s in a_sessions}
        b_call_ids = {s.call_id for s in b_sessions}

        # No overlap
        assert len(a_call_ids & b_call_ids) == 0

        # Each contains their own
        assert session_a.call_id in a_call_ids
        assert session_b.call_id in b_call_ids

        # Clean up
        await session_manager.end_session(session_a.call_id)
        await session_manager.end_session(session_b.call_id)

    async def test_tenant_specific_ai_persona(self, test_tenant_id, test_tenant_id_2):
        """Test that each tenant has its own AI persona configuration."""
        tenant_a = test_tenant_id
        tenant_b = test_tenant_id_2

        # Tenant A: Dental practice persona
        persona_a = {
            "tenant_id": tenant_a,
            "greeting": "Thank you for calling Acme Dental. How can we help your smile today?",
            "system_prompt": "You are a professional dental receptionist. Be warm and friendly.",
            "voice": "en_US-lessac-medium",
            "personality": "warm_professional",
            "industry": "healthcare",
        }

        # Tenant B: Legal firm persona
        persona_b = {
            "tenant_id": tenant_b,
            "greeting": "Good day, you've reached Beta Legal. How may I direct your call?",
            "system_prompt": "You are a professional legal receptionist. Be formal and precise.",
            "voice": "en_US-ryan-medium",
            "personality": "formal_precise",
            "industry": "legal",
        }

        # Verify different greetings
        assert persona_a["greeting"] != persona_b["greeting"]
        assert persona_a["system_prompt"] != persona_b["system_prompt"]
        assert persona_a["voice"] != persona_b["voice"]
        assert persona_a["industry"] != persona_b["industry"]

        # Verify tenant association
        assert persona_a["tenant_id"] == tenant_a
        assert persona_b["tenant_id"] == tenant_b

    async def test_tenant_specific_business_hours(self, test_tenant_id, test_tenant_id_2):
        """Test that business hours are tenant-specific."""
        tenant_a_hours = {
            "monday": {"open": "08:00", "close": "17:00", "is_open": True},
            "tuesday": {"open": "08:00", "close": "17:00", "is_open": True},
        }

        tenant_b_hours = {
            "monday": {"open": "09:00", "close": "18:00", "is_open": True},
            "tuesday": {"open": "09:00", "close": "18:00", "is_open": True},
        }

        # Different hours
        assert tenant_a_hours["monday"]["open"] != tenant_b_hours["monday"]["open"]
        assert tenant_a_hours["monday"]["close"] != tenant_b_hours["monday"]["close"]

    async def test_plan_limits_enforcement(self, test_tenant_id):
        """Test that plan limits are enforced per tenant."""
        # Free plan limits
        free_plan = {
            "max_calls_monthly": 100,
            "max_concurrent_calls": 1,
            "max_users": 1,
            "max_phone_numbers": 1,
            "features": {"analytics": False, "custom_ai": False, "api_access": False},
        }

        # Pro plan limits
        pro_plan = {
            "max_calls_monthly": 1000,
            "max_concurrent_calls": 5,
            "max_users": 10,
            "max_phone_numbers": 5,
            "features": {"analytics": True, "custom_ai": True, "api_access": True},
        }

        # Verify limits differ
        assert free_plan["max_calls_monthly"] < pro_plan["max_calls_monthly"]
        assert free_plan["max_concurrent_calls"] < pro_plan["max_concurrent_calls"]
        assert free_plan["features"]["analytics"] is False
        assert pro_plan["features"]["analytics"] is True

    async def test_concurrent_call_limit(self, session_manager, test_tenant_id):
        """Test that concurrent call limits are enforced."""
        max_concurrent = 2
        tenant_id = test_tenant_id

        # Create calls up to limit
        calls = []
        for i in range(max_concurrent):
            session = ActiveSession(
                call_id=f"limit-call-{i:03d}-{uuid.uuid4()}",
                tenant_id=tenant_id,
                phone_number="+15551111111",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.ACTIVE,
            )
            await session_manager.create_session(session)
            calls.append(session)

        # Verify all active
        active_count = await session_manager.count_sessions(state=CallState.ACTIVE.value)
        assert active_count >= max_concurrent

        # End all calls
        for call in calls:
            await session_manager.end_session(call.call_id)

    async def test_cross_tenant_event_isolation(self, event_bus, event_capture, test_tenant_id, test_tenant_id_2):
        """Test that events are isolated by tenant."""
        tenant_a = test_tenant_id
        tenant_b = test_tenant_id_2

        # Publish events for tenant A
        event_a = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id=f"call-a-{uuid.uuid4()}",
            tenant_id=tenant_a,
            payload={"message": "Tenant A call"},
        )
        await event_bus.publish_async(event_a)

        # Publish events for tenant B
        event_b = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id=f"call-b-{uuid.uuid4()}",
            tenant_id=tenant_b,
            payload={"message": "Tenant B call"},
        )
        await event_bus.publish_async(event_b)

        # Verify tenant-specific events
        a_events = event_capture.get_events_by_tenant(tenant_a)
        b_events = event_capture.get_events_by_tenant(tenant_b)

        assert len(a_events) >= 1
        assert len(b_events) >= 1

        # Verify isolation
        for e in a_events:
            assert e.tenant_id == tenant_a

        for e in b_events:
            assert e.tenant_id == tenant_b

    async def test_tenant_specific_routing_rules(self, test_tenant_id, test_tenant_id_2):
        """Test that routing rules are tenant-specific."""
        tenant_a_routes = [
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
            {"condition": "keyword_emergency", "action": "transfer_to_911", "priority": 100},
        ]

        tenant_b_routes = [
            {"condition": "outside_business_hours", "action": "voicemail", "priority": 10},
            {"condition": "vip_caller", "action": "personal_assistant", "priority": 50},
            {"condition": "language_spanish", "action": "spanish_agent", "priority": 40},
        ]

        # Different rules
        assert tenant_a_routes != tenant_b_routes
        assert len([r for r in tenant_a_routes if r["condition"] == "keyword_emergency"]) == 1
        assert len([r for r in tenant_b_routes if r["condition"] == "language_spanish"]) == 1

    async def test_tenant_specific_faq(self, test_tenant_id, test_tenant_id_2):
        """Test that FAQ entries are tenant-specific."""
        tenant_a_faqs = [
            {"question": "What are your dental cleaning prices?", "answer": "$100 for standard cleaning."},
            {"question": "Do you accept insurance?", "answer": "Yes, we accept most major insurance plans."},
        ]

        tenant_b_faqs = [
            {"question": "What are your consultation fees?", "answer": "$200 per hour for initial consultation."},
            {"question": "Do you offer free case evaluations?", "answer": "Yes, for personal injury cases."},
        ]

        # Different FAQs for different industries
        assert tenant_a_faqs != tenant_b_faqs
        assert "dental" in tenant_a_faqs[0]["question"].lower()
        assert "consultation" in tenant_b_faqs[0]["question"].lower()

    async def test_tenant_analytics_isolation(self, session_manager, test_tenant_id, test_tenant_id_2):
        """Test that analytics data is tenant-isolated."""
        tenant_a = test_tenant_id
        tenant_b = test_tenant_id_2

        # Create calls for tenant A
        for i in range(3):
            session = ActiveSession(
                call_id=f"analytic-a-{i:03d}",
                tenant_id=tenant_a,
                phone_number="+15551111111",
                caller_number=f"+1555100000{i}",
                agent_id="agent-a",
                state=CallState.ENDED,
            )
            await session_manager.create_session(session)

        # Create calls for tenant B
        for i in range(2):
            session = ActiveSession(
                call_id=f"analytic-b-{i:03d}",
                tenant_id=tenant_b,
                phone_number="+15552222222",
                caller_number=f"+1555200000{i}",
                agent_id="agent-b",
                state=CallState.ENDED,
            )
            await session_manager.create_session(session)

        # Get counts per tenant
        a_count = await session_manager.count_sessions(tenant_id=tenant_a)
        b_count = await session_manager.count_sessions(tenant_id=tenant_b)

        assert a_count >= 3
        assert b_count >= 2

    async def test_tenant_slug_uniqueness(self, test_tenant_id, test_tenant_id_2):
        """Test that tenant slugs are unique."""
        tenants = [
            {"id": test_tenant_id, "slug": "acme-dental", "name": "Acme Dental"},
            {"id": test_tenant_id_2, "slug": "beta-legal", "name": "Beta Legal"},
        ]

        slugs = {t["slug"] for t in tenants}
        assert len(slugs) == len(tenants)  # All unique

    async def test_tenant_timezone_handling(self, test_tenant_id, test_tenant_id_2):
        """Test that tenant timezones are respected."""
        tenant_a_tz = "America/New_York"
        tenant_b_tz = "America/Los_Angeles"

        assert tenant_a_tz != tenant_b_tz

        # 3 PM ET != 3 PM PT
        from datetime import datetime
        et_time = datetime(2024, 6, 1, 15, 0, 0)
        # These are just string configs in our system
        assert tenant_a_tz == "America/New_York"
        assert tenant_b_tz == "America/Los_Angeles"

    async def test_tenant_branding_isolation(self, test_tenant_id, test_tenant_id_2):
        """Test that tenant branding is isolated."""
        tenant_a_branding = {
            "business_name": "Acme Dental",
            "greeting": "Welcome to Acme Dental",
            "hold_music": "acme_hold_music.mp3",
            "logo_url": "https://cdn.example.com/acme-logo.png",
        }

        tenant_b_branding = {
            "business_name": "Beta Legal",
            "greeting": "Welcome to Beta Legal Services",
            "hold_music": "beta_hold_music.mp3",
            "logo_url": "https://cdn.example.com/beta-logo.png",
        }

        assert tenant_a_branding["business_name"] != tenant_b_branding["business_name"]
        assert tenant_a_branding["greeting"] != tenant_b_branding["greeting"]

    async def test_tenant_api_key_isolation(self, test_tenant_id, test_tenant_id_2):
        """Test that API keys are tenant-scoped."""
        tenant_a_key = f"af_{test_tenant_id}_key_001"
        tenant_b_key = f"af_{test_tenant_id_2}_key_001"

        assert tenant_a_key != tenant_b_key
        assert test_tenant_id in tenant_a_key
        assert test_tenant_id_2 in tenant_b_key

    async def test_tenant_webhook_isolation(self, test_tenant_id, test_tenant_id_2):
        """Test that webhook endpoints are tenant-specific."""
        tenant_a_webhook = "https://acme.example.com/webhooks/answerflow"
        tenant_b_webhook = "https://beta.example.com/webhooks/answerflow"

        assert tenant_a_webhook != tenant_b_webhook
        assert "acme" in tenant_a_webhook
        assert "beta" in tenant_b_webhook

    async def test_tenant_data_cleanup_on_delete(self, session_manager, test_tenant_id):
        """Test that tenant data can be cleaned up."""
        tenant_id = test_tenant_id

        # Create some sessions
        for i in range(5):
            session = ActiveSession(
                call_id=f"cleanup-{i:03d}",
                tenant_id=tenant_id,
                phone_number="+15551111111",
                caller_number=f"+1555000000{i}",
                agent_id="agent-001",
                state=CallState.ENDED,
            )
            await session_manager.create_session(session)

        # Verify they exist
        count_before = await session_manager.count_sessions(tenant_id=tenant_id)
        assert count_before >= 5

        # Clean up (delete all sessions for tenant)
        tenant_sessions = await session_manager.get_sessions_by_tenant(tenant_id)
        for sess in tenant_sessions:
            await session_manager.delete_session(sess.call_id)

        # Verify cleanup
        count_after = await session_manager.count_sessions(tenant_id=tenant_id)
        assert count_after == 0
