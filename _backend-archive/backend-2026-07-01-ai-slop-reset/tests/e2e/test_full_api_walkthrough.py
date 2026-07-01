"""
test_full_api_walkthrough.py - Complete walkthrough of every API endpoint.

Tests the full API surface:
    - Auth: register, login, refresh, logout, password reset
    - Calls: list, detail, transcript, recording, tags
    - Messages: CRUD, read/unread, forward, resolve
    - Appointments: list, create, update, cancel, availability
    - Business: profile, AI config, FAQ, routing rules
    - Integrations: list, connect, sync, webhooks
    - Team: members, invites, preferences
    - Admin: tenants, health, stats, audit log

Uses httpx.AsyncClient against the FastAPI test server.

Location: backend/tests/e2e/test_full_api_walkthrough.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from fastapi import status

from tests.e2e.walkthrough_http import (
    API_PREFIX,
    app_client,
    authed_app_client,
    running_app,
    super_admin_app_client,
)

pytestmark = pytest.mark.asyncio


# Each router self-prefixes (e.g. /auth); mount point is API_PREFIX only.
AUTH_PREFIX = f"{API_PREFIX}/auth"
CALLS_PREFIX = f"{API_PREFIX}/calls"
MESSAGES_PREFIX = f"{API_PREFIX}/messages"
APPOINTMENTS_PREFIX = f"{API_PREFIX}/appointments"
BUSINESS_PREFIX = f"{API_PREFIX}/business"
INTEGRATIONS_PREFIX = f"{API_PREFIX}/integrations"
TEAM_PREFIX = f"{API_PREFIX}/team"
ADMIN_PREFIX = f"{API_PREFIX}/admin"


class TestAuthFlow:
    """Test authentication flow endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        """Create async test client."""
        async with app_client(running_app) as client:
            yield client

    async def test_register_new_account(self, client):
        """POST /auth/register - Create new business account."""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "business_name": "Test Business",
            "phone_number": "+15551234567",
            "timezone": "America/New_York",
        }
        resp = await client.post(f"{AUTH_PREFIX}/register", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        assert "user" in data["data"]
        assert "tenant" in data["data"]
        assert "tokens" in data["data"]
        assert "id" in data["data"]["user"]
        assert "id" in data["data"]["tenant"]

    async def test_register_duplicate_email(self, client):
        """POST /auth/register - Reject duplicate email."""
        email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": email,
            "password": "SecurePass123!",
            "business_name": "Test Business",
            "phone_number": "+15551234567",
        }
        resp1 = await client.post(f"{AUTH_PREFIX}/register", json=payload)
        assert resp1.status_code == status.HTTP_201_CREATED

        # Duplicate should fail
        resp2 = await client.post(f"{AUTH_PREFIX}/register", json=payload)
        assert resp2.status_code == status.HTTP_409_CONFLICT

    async def test_login_success(self, client):
        """POST /auth/login - Successful login returns tokens."""
        # First register
        email = f"login_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass123!"
        await client.post(f"{AUTH_PREFIX}/register", json={
            "email": email,
            "password": password,
            "business_name": "Login Test",
            "phone_number": "+15551234567",
        })

        resp = await client.post(f"{AUTH_PREFIX}/login", json={
            "email": email,
            "password": password,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "tokens" in data["data"]
        assert "access_token" in data["data"]["tokens"]
        assert "refresh_token" in data["data"]["tokens"]

    async def test_login_invalid_credentials(self, client):
        """POST /auth/login - Reject invalid credentials."""
        resp = await client.post(f"{AUTH_PREFIX}/login", json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_token(self, client):
        """POST /auth/refresh - Refresh access token."""
        # Register and login
        email = f"refresh_{uuid.uuid4().hex[:8]}@example.com"
        await client.post(f"{AUTH_PREFIX}/register", json={
            "email": email,
            "password": "SecurePass123!",
            "business_name": "Refresh Test",
            "phone_number": "+15551234567",
        })
        login_resp = await client.post(f"{AUTH_PREFIX}/login", json={
            "email": email,
            "password": "SecurePass123!",
        })
        refresh_token = login_resp.json()["data"]["tokens"]["refresh_token"]

        resp = await client.post(f"{AUTH_PREFIX}/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    async def test_forgot_password(self, client):
        """POST /auth/forgot-password - Request password reset."""
        resp = await client.post(f"{AUTH_PREFIX}/forgot-password", json={
            "email": "user@example.com",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_reset_password(self, client):
        """POST /auth/reset-password - Reset password with token."""
        # Register first
        email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
        await client.post(f"{AUTH_PREFIX}/register", json={
            "email": email,
            "password": "OldPass123!",
            "business_name": "Reset Test",
            "phone_number": "+15551234567",
        })

        resp = await client.post(f"{AUTH_PREFIX}/reset-password", json={
            "token": "test_token_123",
            "new_password": "NewPass123!",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_magic_link_request(self, client):
        """POST /auth/magic-link - Request magic link."""
        resp = await client.post(f"{AUTH_PREFIX}/magic-link", json={
            "email": "user@example.com",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_verify_email(self, client):
        """POST /auth/verify-email - Verify email address."""
        resp = await client.post(f"{AUTH_PREFIX}/verify-email", json={
            "token": "test_verification_token",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestCallsAPI:
    """Test call management API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with authed_app_client(running_app, seed_calls=3) as client:
            yield client

    async def test_list_calls(self, client):
        """GET /calls - List calls with pagination."""
        resp = await client.get(f"{CALLS_PREFIX}?page=1&per_page=10")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_list_calls_with_filters(self, client):
        """GET /calls - List calls with status filter."""
        resp = await client.get(f"{CALLS_PREFIX}?status=ended&direction=inbound")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_live_calls(self, client):
        """GET /calls/live - Get active calls."""
        resp = await client.get(f"{CALLS_PREFIX}/live")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "calls" in data["data"]

    async def test_get_call_summary(self, client):
        """GET /calls/summary - Get call statistics."""
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        resp = await client.get(
            f"{CALLS_PREFIX}/summary?start_date={start.isoformat()}&end_date={end.isoformat()}"
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "total_calls" in data["data"]

    async def test_get_call_detail(self, client):
        """GET /calls/{call_id} - Get call detail."""
        # First list to get an ID
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.get(f"{CALLS_PREFIX}/{call_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]

    async def test_update_call_tags(self, client):
        """PATCH /calls/{call_id} - Update call tags."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.patch(f"{CALLS_PREFIX}/{call_id}", json={
            "tags": ["important", "follow-up"],
            "notes": "Customer interested in upgrade",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_transfer_call(self, client):
        """POST /calls/{call_id}/transfer - Transfer call."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.post(f"{CALLS_PREFIX}/{call_id}/transfer", json={
            "destination": "+15559998888",
            "transfer_type": "attended",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_add_call_tags(self, client):
        """POST /calls/{call_id}/tags - Add tags."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.post(f"{CALLS_PREFIX}/{call_id}/tags", json={
            "tags": ["sales", "callback"],
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_remove_call_tag(self, client):
        """DELETE /calls/{call_id}/tags/{tag} - Remove tag."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        # First add a tag
        await client.post(f"{CALLS_PREFIX}/{call_id}/tags", json={"tags": ["temp"]})

        # Then remove it
        resp = await client.delete(f"{CALLS_PREFIX}/{call_id}/tags/temp")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_call_transcript(self, client):
        """GET /calls/{call_id}/transcript - Get transcript."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.get(f"{CALLS_PREFIX}/{call_id}/transcript")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "entries" in data["data"]

    async def test_get_recording_url(self, client):
        """GET /calls/{call_id}/recording - Get recording URL."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        assert list_resp.status_code == status.HTTP_200_OK
        items = list_resp.json()["data"]["items"]
        with_recording = [i for i in items if i.get("recording_url")]
        assert with_recording, (
            "seed_calls_for_tenant must seed a Recording with access_url on the first call"
        )
        call_id = with_recording[0]["id"]
        resp = await client.get(f"{CALLS_PREFIX}/{call_id}/recording")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_control_recording(self, client):
        """POST /calls/{call_id}/recording - Control recording."""
        list_resp = await client.get(f"{CALLS_PREFIX}")
        call_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.post(f"{CALLS_PREFIX}/{call_id}/recording", json={
            "action": "start",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestMessagesAPI:
    """Test message management API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with authed_app_client(running_app) as client:
            yield client

    async def test_list_messages(self, client):
        """GET /messages - List messages."""
        resp = await client.get(f"{MESSAGES_PREFIX}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_list_messages_with_filters(self, client):
        """GET /messages - Filter by read status."""
        resp = await client.get(f"{MESSAGES_PREFIX}?is_read=false")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_list_messages_with_search(self, client):
        """GET /messages - Search messages."""
        resp = await client.get(f"{MESSAGES_PREFIX}?search=service")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_message_stats(self, client):
        """GET /messages/stats - Get message statistics."""
        resp = await client.get(f"{MESSAGES_PREFIX}/stats")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "total_messages" in data["data"]

    async def test_create_message(self, client):
        """POST /messages - Create message."""
        resp = await client.post(f"{MESSAGES_PREFIX}", json={
            "call_id": str(uuid.uuid4()),
            "channel": "voice",
            "priority": "normal",
            "contact": {
                "name": "Test Caller",
                "phone": "+15551234567",
                "email": "test@example.com",
                "company": None,
                "best_time_to_call": "Morning",
            },
            "subject": "Test message",
            "body": "This is a test message created via API.",
            "tags": ["test", "api"],
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]

    async def test_get_message(self, client):
        """GET /messages/{message_id} - Get message detail."""
        # Create first
        create_resp = await client.post(f"{MESSAGES_PREFIX}", json={
            "call_id": str(uuid.uuid4()),
            "channel": "voice",
            "priority": "normal",
            "contact": {"name": "Test", "phone": "+15551234567"},
            "subject": "Test",
            "body": "Test body",
            "tags": ["test"],
        })
        msg_id = create_resp.json()["data"]["id"]

        resp = await client.get(f"{MESSAGES_PREFIX}/{msg_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == msg_id

    async def test_update_message(self, client):
        """PATCH /messages/{message_id} - Update message."""
        create_resp = await client.post(f"{MESSAGES_PREFIX}", json={
            "call_id": str(uuid.uuid4()),
            "channel": "voice",
            "priority": "normal",
            "contact": {"name": "Test", "phone": "+15551234567"},
            "subject": "Original",
            "body": "Original body",
            "tags": ["test"],
        })
        msg_id = create_resp.json()["data"]["id"]

        resp = await client.patch(f"{MESSAGES_PREFIX}/{msg_id}", json={
            "priority": "high",
            "subject": "Updated subject",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_mark_message_read(self, client):
        """POST /messages/{message_id}/read - Mark as read."""
        list_resp = await client.get(f"{MESSAGES_PREFIX}?is_read=false")
        items = list_resp.json()["data"]["items"]
        if items:
            msg_id = items[0]["id"]
            resp = await client.post(f"{MESSAGES_PREFIX}/{msg_id}/read", json={"is_read": True})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["success"] is True

    async def test_resolve_message(self, client):
        """PATCH /messages/{message_id}/resolve - Resolve message."""
        create_resp = await client.post(f"{MESSAGES_PREFIX}", json={
            "call_id": str(uuid.uuid4()),
            "channel": "voice",
            "priority": "normal",
            "contact": {"name": "Test", "phone": "+15551234567"},
            "body": "Resolve me",
            "tags": ["test"],
        })
        msg_id = create_resp.json()["data"]["id"]

        resp = await client.patch(f"{MESSAGES_PREFIX}/{msg_id}/resolve", json={
            "resolution_note": "Resolved via API test",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_forward_message(self, client):
        """POST /messages/{message_id}/forward - Forward message."""
        create_resp = await client.post(f"{MESSAGES_PREFIX}", json={
            "call_id": str(uuid.uuid4()),
            "channel": "voice",
            "priority": "normal",
            "contact": {"name": "Test", "phone": "+15551234567"},
            "body": "Forward me",
            "tags": ["test"],
        })
        msg_id = create_resp.json()["data"]["id"]

        resp = await client.post(f"{MESSAGES_PREFIX}/{msg_id}/forward", json={
            "destinations": ["admin@example.com", "manager@example.com"],
            "note": "Please review",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_delete_message(self, client):
        """DELETE /messages/{message_id} - Delete message."""
        create_resp = await client.post(f"{MESSAGES_PREFIX}", json={
            "call_id": str(uuid.uuid4()),
            "channel": "voice",
            "priority": "normal",
            "contact": {"name": "Test", "phone": "+15551234567"},
            "body": "Delete me",
            "tags": ["test"],
        })
        msg_id = create_resp.json()["data"]["id"]

        resp = await client.delete(f"{MESSAGES_PREFIX}/{msg_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestAppointmentsAPI:
    """Test appointment management API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with authed_app_client(running_app) as client:
            yield client

    async def test_list_appointments(self, client):
        """GET /appointments - List appointments."""
        resp = await client.get(f"{APPOINTMENTS_PREFIX}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]

    async def test_list_appointments_with_filters(self, client):
        """GET /appointments - Filter by status."""
        resp = await client.get(f"{APPOINTMENTS_PREFIX}?status=confirmed")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_appointment_stats(self, client):
        """GET /appointments/stats - Get appointment statistics."""
        resp = await client.get(f"{APPOINTMENTS_PREFIX}/stats")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "total_appointments" in data["data"]

    async def test_create_appointment(self, client):
        """POST /appointments - Create appointment."""
        tomorrow = date.today() + timedelta(days=1)
        resp = await client.post(f"{APPOINTMENTS_PREFIX}", json={
            "contact": {
                "name": "Jane Patient",
                "phone": "+15551234567",
                "email": "jane@example.com",
            },
            "service": {
                "name": "Dental Cleaning",
                "duration_minutes": 30,
                "price": "$100",
                "description": "Standard cleaning",
            },
            "appointment_date": tomorrow.isoformat(),
            "start_time": "10:30:00",
            "end_time": "11:00:00",
            "timezone": "America/New_York",
            "notes": "First-time patient",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]

    async def test_get_appointment(self, client):
        """GET /appointments/{appointment_id} - Get appointment."""
        # Create first
        create_resp = await client.post(f"{APPOINTMENTS_PREFIX}", json={
            "contact": {"name": "Test", "phone": "+15551234567"},
            "service": {"name": "Checkup", "duration_minutes": 30},
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "09:30:00",
            "timezone": "America/New_York",
        })
        appt_id = create_resp.json()["data"]["id"]

        resp = await client.get(f"{APPOINTMENTS_PREFIX}/{appt_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == appt_id

    async def test_update_appointment(self, client):
        """PATCH /appointments/{appointment_id} - Update appointment."""
        create_resp = await client.post(f"{APPOINTMENTS_PREFIX}", json={
            "contact": {"name": "Test", "phone": "+15551234567"},
            "service": {"name": "Checkup", "duration_minutes": 30},
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "09:30:00",
            "timezone": "America/New_York",
        })
        appt_id = create_resp.json()["data"]["id"]

        resp = await client.patch(f"{APPOINTMENTS_PREFIX}/{appt_id}", json={
            "status": "confirmed",
            "notes": "Updated notes",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_cancel_appointment(self, client):
        """POST /appointments/{appointment_id}/cancel - Cancel appointment."""
        create_resp = await client.post(f"{APPOINTMENTS_PREFIX}", json={
            "contact": {"name": "Test", "phone": "+15551234567"},
            "service": {"name": "Checkup", "duration_minutes": 30},
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "09:30:00",
            "timezone": "America/New_York",
        })
        appt_id = create_resp.json()["data"]["id"]

        resp = await client.post(f"{APPOINTMENTS_PREFIX}/{appt_id}/cancel", json={
            "reason": "Patient request",
            "notify_contact": True,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_availability(self, client):
        """GET /appointments/availability/slots - Check availability."""
        start = date.today() + timedelta(days=1)
        end = date.today() + timedelta(days=7)
        resp = await client.get(
            f"{APPOINTMENTS_PREFIX}/availability/slots?start_date={start.isoformat()}&end_date={end.isoformat()}&service_duration=30"
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "days" in data["data"]

    async def test_get_business_hours(self, client):
        """GET /appointments/business-hours/config - Get business hours."""
        resp = await client.get(f"{APPOINTMENTS_PREFIX}/business-hours/config")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "hours" in data["data"]
        assert "timezone" in data["data"]

    async def test_update_business_hours(self, client):
        """PUT /appointments/business-hours/config - Update business hours."""
        resp = await client.put(f"{APPOINTMENTS_PREFIX}/business-hours/config", json={
            "timezone": "America/Chicago",
            "hours": [
                {"day": "monday", "is_open": True, "open_time": "08:00:00", "close_time": "17:00:00", "breaks": []},
                {"day": "tuesday", "is_open": True, "open_time": "08:00:00", "close_time": "17:00:00", "breaks": []},
            ],
            "holidays": [],
            "appointment_interval_minutes": 30,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestBusinessAPI:
    """Test business settings API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with authed_app_client(running_app) as client:
            yield client

    async def test_get_business_profile(self, client):
        """GET /business/profile - Get business profile."""
        resp = await client.get(f"{BUSINESS_PREFIX}/profile")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "name" in data["data"]

    async def test_update_business_profile(self, client):
        """PATCH /business/profile - Update business profile."""
        resp = await client.patch(f"{BUSINESS_PREFIX}/profile", json={
            "name": "Updated Business Name",
            "phone_number": "+15559876543",
            "email": "updated@example.com",
            "timezone": "America/Chicago",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_business_settings(self, client):
        """GET /business/settings - Get combined business settings."""
        resp = await client.get(f"{BUSINESS_PREFIX}/settings")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_voice_config(self, client):
        """GET /business/ai/voice - Get voice config."""
        resp = await client.get(f"{BUSINESS_PREFIX}/ai/voice")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_update_voice_config(self, client):
        """PATCH /business/ai/voice - Update voice config."""
        resp = await client.patch(f"{BUSINESS_PREFIX}/ai/voice", json={
            "speaking_rate": 1.2,
            "personality": "warm_friendly",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_handling_config(self, client):
        """GET /business/ai/handling - Get handling config."""
        resp = await client.get(f"{BUSINESS_PREFIX}/ai/handling")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_update_handling_config(self, client):
        """PATCH /business/ai/handling - Update handling config."""
        resp = await client.patch(f"{BUSINESS_PREFIX}/ai/handling", json={
            "max_call_duration_minutes": 45,
            "enable_call_recording": True,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_list_faq(self, client):
        """GET /business/faq - List FAQ entries."""
        resp = await client.get(f"{BUSINESS_PREFIX}/faq")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]

    async def test_list_faq_with_category(self, client):
        """GET /business/faq?category= - Filter FAQ by category."""
        resp = await client.get(f"{BUSINESS_PREFIX}/faq?category=hours")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_create_faq(self, client):
        """POST /business/faq - Create FAQ entry."""
        resp = await client.post(f"{BUSINESS_PREFIX}/faq", json={
            "question": "Do you accept walk-ins?",
            "answer": "Yes, we accept walk-ins but appointments are preferred.",
            "category": "general",
            "tags": ["walk-in", "appointments"],
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]

    async def test_get_faq(self, client):
        """GET /business/faq/{faq_id} - Get FAQ."""
        create_resp = await client.post(f"{BUSINESS_PREFIX}/faq", json={
            "question": "Get FAQ test?",
            "answer": "Get FAQ answer.",
            "category": "test",
            "tags": ["test"],
        })
        faq_id = create_resp.json()["data"]["id"]

        resp = await client.get(f"{BUSINESS_PREFIX}/faq/{faq_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == faq_id

    async def test_update_faq(self, client):
        """PATCH /business/faq/{faq_id} - Update FAQ."""
        create_resp = await client.post(f"{BUSINESS_PREFIX}/faq", json={
            "question": "Update FAQ test?",
            "answer": "Original answer.",
            "category": "test",
            "tags": ["test"],
        })
        faq_id = create_resp.json()["data"]["id"]

        resp = await client.patch(f"{BUSINESS_PREFIX}/faq/{faq_id}", json={
            "answer": "Updated answer text.",
            "is_active": True,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_delete_faq(self, client):
        """DELETE /business/faq/{faq_id} - Delete FAQ."""
        create_resp = await client.post(f"{BUSINESS_PREFIX}/faq", json={
            "question": "Temp question?",
            "answer": "Temp answer.",
            "category": "temp",
            "tags": ["temp"],
        })
        faq_id = create_resp.json()["data"]["id"]

        resp = await client.delete(f"{BUSINESS_PREFIX}/faq/{faq_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_bulk_import_faq(self, client):
        """POST /business/faq/import - Bulk import FAQ."""
        resp = await client.post(f"{BUSINESS_PREFIX}/faq/import", json={
            "replace_existing": False,
            "entries": [
                {"question": "Q1?", "answer": "A1.", "category": "test", "tags": ["test1"]},
                {"question": "Q2?", "answer": "A2.", "category": "test", "tags": ["test2"]},
            ],
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["imported_count"] == 2

    async def test_get_routing_rules(self, client):
        """GET /business/routing - Get routing rules."""
        resp = await client.get(f"{BUSINESS_PREFIX}/routing")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_update_routing_rules(self, client):
        """PUT /business/routing - Update routing rules."""
        resp = await client.put(f"{BUSINESS_PREFIX}/routing", json={
            "rules": [
                {"name": "After Hours", "condition": "outside_business_hours", "action": "ai_answer", "priority": 10, "is_active": True},
                {"name": "VIP", "condition": "vip_caller", "action": "priority_queue", "priority": 50, "is_active": True},
            ],
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestIntegrationsAPI:
    """Test integration management API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with authed_app_client(running_app) as client:
            yield client

    async def test_list_integrations(self, client):
        """GET /integrations - List integrations."""
        resp = await client.get(f"{INTEGRATIONS_PREFIX}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_available_integrations(self, client):
        """GET /integrations/available - List available types."""
        resp = await client.get(f"{INTEGRATIONS_PREFIX}/available")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

    async def test_oauth_initiate(self, client):
        """POST /integrations/oauth/initiate - Start OAuth."""
        resp = await client.post(f"{INTEGRATIONS_PREFIX}/oauth/initiate", json={
            "integration_type": "google_calendar",
            "redirect_uri": "https://example.com/callback",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "auth_url" in data["data"]
        assert "state" in data["data"]

    async def test_list_webhook_endpoints(self, client):
        """GET /integrations/webhooks/list - List webhooks."""
        resp = await client.get(f"{INTEGRATIONS_PREFIX}/webhooks/list")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


class TestTeamAPI:
    """Test team management API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with authed_app_client(running_app) as client:
            yield client

    async def test_list_team_members(self, client):
        """GET /team/members - List team members."""
        resp = await client.get(f"{TEAM_PREFIX}/members")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_invite_team_member(self, client):
        """POST /team/members - Invite member."""
        resp = await client.post(f"{TEAM_PREFIX}/members", json={
            "email": f"new_member_{uuid.uuid4().hex[:6]}@example.com",
            "first_name": "New",
            "last_name": "Member",
            "role": "agent",
            "department": "Support",
            "send_invite": True,
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]

    async def test_get_team_member(self, client):
        """GET /team/members/{member_id} - Get member."""
        list_resp = await client.get(f"{TEAM_PREFIX}/members")
        member_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.get(f"{TEAM_PREFIX}/members/{member_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == member_id

    async def test_update_team_member(self, client):
        """PATCH /team/members/{member_id} - Update member."""
        list_resp = await client.get(f"{TEAM_PREFIX}/members")
        member_id = list_resp.json()["data"]["items"][0]["id"]

        resp = await client.patch(f"{TEAM_PREFIX}/members/{member_id}", json={
            "role": "manager",
            "department": "Management",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_remove_team_member(self, client):
        """DELETE /team/members/{member_id} - Remove member."""
        # Create a member to remove
        create_resp = await client.post(f"{TEAM_PREFIX}/members", json={
            "email": f"to_remove_{uuid.uuid4().hex[:6]}@example.com",
            "first_name": "To",
            "last_name": "Remove",
            "role": "viewer",
        })
        member_id = create_resp.json()["data"]["id"]

        resp = await client.delete(f"{TEAM_PREFIX}/members/{member_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_send_invite(self, client):
        """POST /team/invites - Send invite."""
        resp = await client.post(f"{TEAM_PREFIX}/invites", json={
            "email": "invitee@example.com",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_notification_preferences(self, client):
        """GET /team/notifications/preferences - Get preferences."""
        resp = await client.get(f"{TEAM_PREFIX}/notifications/preferences")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_update_notification_preferences(self, client):
        """PUT /team/notifications/preferences - Update preferences."""
        resp = await client.put(f"{TEAM_PREFIX}/notifications/preferences", json={
            "email_new_calls": True,
            "email_new_messages": False,
            "email_new_appointments": True,
            "email_daily_digest": True,
            "sms_urgent_only": True,
            "slack_notifications": False,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestAdminAPI:
    """Test admin API endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with super_admin_app_client(running_app) as client:
            yield client

    async def test_list_tenants(self, client):
        """GET /admin/tenants - List tenants."""
        resp = await client.get(f"{ADMIN_PREFIX}/tenants")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_list_tenants_with_filters(self, client):
        """GET /admin/tenants - Filter tenants."""
        resp = await client.get(f"{ADMIN_PREFIX}/tenants?plan=free&is_active=true")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_create_tenant(self, client):
        """POST /admin/tenants - Create tenant."""
        resp = await client.post(f"{ADMIN_PREFIX}/tenants", json={
            "name": "Test Tenant",
            "slug": f"test-tenant-{uuid.uuid4().hex[:6]}",
            "owner_email": "owner@example.com",
            "timezone": "America/New_York",
            "plan": "starter",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]

    async def test_get_tenant(self, client):
        """GET /admin/tenants/{tenant_id} - Get tenant."""
        list_resp = await client.get(f"{ADMIN_PREFIX}/tenants")
        tenant_id = list_resp.json()["data"][0]["id"]

        resp = await client.get(f"{ADMIN_PREFIX}/tenants/{tenant_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == tenant_id

    async def test_update_tenant(self, client):
        """PATCH /admin/tenants/{tenant_id} - Update tenant."""
        list_resp = await client.get(f"{ADMIN_PREFIX}/tenants")
        tenant_id = list_resp.json()["data"][0]["id"]

        resp = await client.patch(f"{ADMIN_PREFIX}/tenants/{tenant_id}", json={
            "plan": "pro",
            "is_active": True,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_delete_tenant(self, client):
        """DELETE /admin/tenants/{tenant_id} - Delete tenant."""
        # Create a tenant to delete
        create_resp = await client.post(f"{ADMIN_PREFIX}/tenants", json={
            "name": "To Delete",
            "slug": f"to-delete-{uuid.uuid4().hex[:6]}",
            "owner_email": "delete@example.com",
            "timezone": "America/New_York",
            "plan": "free",
        })
        tenant_id = create_resp.json()["data"]["id"]

        resp = await client.delete(f"{ADMIN_PREFIX}/tenants/{tenant_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_system_health(self, client):
        """GET /admin/health - System health."""
        resp = await client.get(f"{ADMIN_PREFIX}/health")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "services" in data["data"]
        assert "status" in data["data"]

    async def test_system_stats(self, client):
        """GET /admin/stats - System statistics."""
        resp = await client.get(f"{ADMIN_PREFIX}/stats")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "total_tenants" in data["data"]
        assert "active_tenants" in data["data"]

    async def test_usage_reports(self, client):
        """GET /admin/usage - Usage reports."""
        resp = await client.get(f"{ADMIN_PREFIX}/usage")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "usage_by_tenant" in data["data"]

    async def test_audit_log(self, client):
        """GET /admin/audit-log - Audit log."""
        resp = await client.get(f"{ADMIN_PREFIX}/audit-log")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_audit_log_with_filters(self, client):
        """GET /admin/audit-log - Filter audit log."""
        resp = await client.get(f"{ADMIN_PREFIX}/audit-log?action=user.login")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True

    async def test_get_rate_limit_status(self, client):
        """GET /admin/rate-limits/{tenant_id} - Rate limit status."""
        list_resp = await client.get(f"{ADMIN_PREFIX}/tenants")
        tenant_id = list_resp.json()["data"][0]["id"]

        resp = await client.get(f"{ADMIN_PREFIX}/rate-limits/{tenant_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "requests_this_minute" in data["data"]

    async def test_update_rate_limits(self, client):
        """PUT /admin/rate-limits/{tenant_id} - Update rate limits."""
        list_resp = await client.get(f"{ADMIN_PREFIX}/tenants")
        tenant_id = list_resp.json()["data"][0]["id"]

        resp = await client.put(f"{ADMIN_PREFIX}/rate-limits/{tenant_id}", json={
            "requests_per_minute": 200,
            "requests_per_hour": 10000,
            "concurrent_calls": 10,
            "webhook_calls_per_minute": 50,
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True


class TestHealthAndRoot:
    """Test health check and root endpoints."""

    @pytest.fixture
    async def client(self, running_app):
        async with app_client(running_app) as client:
            yield client

    async def test_health_check(self, client):
        """GET /health - Health check."""
        resp = await client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "ok")
        assert "timestamp" in data
        assert "checks" in data

    async def test_root_endpoint(self, client):
        """GET / - Root endpoint."""
        resp = await client.get("/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "name" in data
        assert "version" in data

    async def test_openapi_schema(self, client):
        """GET /openapi.json - OpenAPI schema."""
        resp = await client.get("/openapi.json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data

    async def test_docs_endpoint(self, client):
        """GET /docs - Swagger UI."""
        resp = await client.get("/docs")
        assert resp.status_code == status.HTTP_200_OK
        assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()


class TestAPIHeadersAndMiddleware:
    """Test middleware headers and rate limiting."""

    @pytest.fixture
    async def client(self, running_app):
        async with app_client(running_app) as client:
            yield client

    async def test_response_headers(self, client):
        """Test that response includes timing and request ID headers."""
        resp = await client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        assert "X-Response-Time" in resp.headers

    async def test_cors_headers(self, client):
        """Test CORS headers on response."""
        resp = await client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access-control-allow-origin" in resp.headers

    async def test_error_response_format(self, client):
        """Test that error responses follow the standard format."""
        resp = await client.get(f"{CALLS_PREFIX}/nonexistent-uuid")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or resp.status_code == status.HTTP_404_NOT_FOUND
        data = resp.json()
        assert "success" in data or "error" in data or "detail" in data

    async def test_pagination_params(self, client, running_app):
        """Test pagination parameters are respected."""
        async with authed_app_client(running_app, seed_calls=5) as authed:
            resp = await authed.get(f"{CALLS_PREFIX}?page=1&per_page=5")
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            if "items" in data.get("data", {}):
                assert len(data["data"]["items"]) <= 5
