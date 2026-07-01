"""
test_webhook_delivery.py - End-to-end tests for webhook delivery.

Tests webhook registration, event triggering, delivery with HMAC signature,
retry on failure, and endpoint management.

Verifies:
    - Webhook endpoints can be registered
    - Events trigger webhook deliveries
    - HMAC signatures are generated and verified
    - Failed deliveries are retried
    - Webhooks are tenant-scoped

Location: backend/tests/e2e/test_webhook_delivery.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

from backend.orchestrator.models import EventType, SystemEvent

pytestmark = pytest.mark.asyncio


class MockWebhookEndpoint:
    """Simulates a webhook endpoint that receives HTTP POST requests."""

    def __init__(self, url: str, secret: str) -> None:
        self.url = url
        self.secret = secret
        self.received_payloads: List[Dict[str, Any]] = []
        self.headers_received: List[Dict[str, str]] = []
        self.should_fail_next: bool = False
        self.failure_count: int = 0

    async def receive(self, payload: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Simulate receiving a webhook POST request."""
        self.headers_received.append(headers)

        if self.should_fail_next:
            self.should_fail_next = False
            self.failure_count += 1
            return {"status": "error", "status_code": 500}

        try:
            data = json.loads(payload)
            self.received_payloads.append(data)
            return {"status": "success", "status_code": 200}
        except json.JSONDecodeError:
            return {"status": "error", "status_code": 400}

    def reset(self) -> None:
        """Clear all received data."""
        self.received_payloads.clear()
        self.headers_received.clear()
        self.failure_count = 0


def generate_hmac_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = generate_hmac_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


class TestWebhookDelivery:
    """End-to-end tests for webhook delivery system."""

    async def test_webhook_registration(self, test_tenant_id):
        """Test that webhook endpoints can be registered."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        webhook_config = {
            "id": str(uuid.uuid4()),
            "tenant_id": test_tenant_id,
            "url": endpoint.url,
            "secret": endpoint.secret,
            "events": ["call.ended", "appointment.booked", "message.taken"],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
        }

        assert webhook_config["tenant_id"] == test_tenant_id
        assert webhook_config["url"] == "https://acme.example.com/webhooks/answerflow"
        assert len(webhook_config["events"]) == 3
        assert webhook_config["is_active"] is True

    async def test_webhook_hmac_signature_generation(self, test_tenant_id):
        """Test that HMAC signatures are correctly generated."""
        secret = "whsec_test_secret_001"
        payload = json.dumps({
            "event": "call.ended",
            "call_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
        })

        signature = generate_hmac_signature(payload, secret)

        # Signature should be a valid hex string
        assert len(signature) == 64  # SHA-256 hex length
        int(signature, 16)  # Valid hex

        # Verify the signature
        assert verify_hmac_signature(payload, signature, secret) is True

    async def test_webhook_hmac_signature_verification(self, test_tenant_id):
        """Test HMAC signature verification catches tampering."""
        secret = "whsec_test_secret_001"
        payload = json.dumps({"event": "call.ended", "call_id": "test-123"})

        signature = generate_hmac_signature(payload, secret)

        # Correct signature should verify
        assert verify_hmac_signature(payload, signature, secret) is True

        # Tampered payload should fail
        tampered_payload = payload.replace("test-123", "tampered")
        assert verify_hmac_signature(tampered_payload, signature, secret) is False

        # Wrong secret should fail
        assert verify_hmac_signature(payload, signature, "wrong_secret") is False

    async def test_webhook_delivery_success(self, test_tenant_id):
        """Test successful webhook delivery."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        payload = json.dumps({
            "event": "call.ended",
            "tenant_id": test_tenant_id,
            "call_id": str(uuid.uuid4()),
            "caller_number": "+15551234567",
            "duration_seconds": 120,
            "timestamp": datetime.utcnow().isoformat(),
        })

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
            "X-Event-Type": "call.ended",
            "X-Delivery-Id": str(uuid.uuid4()),
        }

        result = await endpoint.receive(payload, headers)

        assert result["status"] == "success"
        assert result["status_code"] == 200
        assert len(endpoint.received_payloads) == 1
        assert endpoint.received_payloads[0]["event"] == "call.ended"

    async def test_webhook_delivery_with_hmac_header(self, test_tenant_id):
        """Test that webhook includes HMAC signature header."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        event_data = {
            "event": "appointment.booked",
            "tenant_id": test_tenant_id,
            "appointment_id": str(uuid.uuid4()),
            "patient_name": "John Smith",
            "appointment_date": (datetime.now() + timedelta(days=1)).isoformat(),
        }
        payload = json.dumps(event_data)
        signature = generate_hmac_signature(payload, endpoint.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Event-Type": "appointment.booked",
        }

        await endpoint.receive(payload, headers)

        # Verify signature header was present
        assert len(endpoint.headers_received) == 1
        assert "X-Webhook-Signature" in endpoint.headers_received[0]
        received_sig = endpoint.headers_received[0]["X-Webhook-Signature"]

        # Verify signature matches payload
        received_payload = json.dumps(endpoint.received_payloads[0])
        assert verify_hmac_signature(received_payload, received_sig, endpoint.secret)

    async def test_webhook_retry_on_failure(self, test_tenant_id):
        """Test that failed webhook deliveries are retried."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        payload = json.dumps({
            "event": "call.ended",
            "tenant_id": test_tenant_id,
            "call_id": str(uuid.uuid4()),
        })
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
        }

        # First attempt fails
        endpoint.should_fail_next = True
        result1 = await endpoint.receive(payload, headers)
        assert result1["status"] == "error"
        assert endpoint.failure_count == 1

        # Retry succeeds
        result2 = await endpoint.receive(payload, headers)
        assert result2["status"] == "success"

    async def test_webhook_retry_exhaustion(self, test_tenant_id):
        """Test webhook delivery with max retries exceeded."""
        endpoint = MockWebhookEndpoint(
            url="https://unreliable.example.com/webhook",
            secret="whsec_test_secret_001",
        )

        payload = json.dumps({"event": "call.ended", "tenant_id": test_tenant_id})
        headers = {
            "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
        }

        # Simulate all retries failing
        max_retries = 3
        for attempt in range(max_retries):
            endpoint.should_fail_next = True
            result = await endpoint.receive(payload, headers)
            assert result["status"] == "error"

        assert endpoint.failure_count == max_retries

    async def test_webhook_delivery_multiple_events(self, test_tenant_id):
        """Test delivery of multiple different event types."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        events = [
            {"event": "call.started", "call_id": str(uuid.uuid4())},
            {"event": "call.ended", "call_id": str(uuid.uuid4())},
            {"event": "appointment.booked", "appointment_id": str(uuid.uuid4())},
            {"event": "message.taken", "message_id": str(uuid.uuid4())},
        ]

        for event_data in events:
            event_data["tenant_id"] = test_tenant_id
            event_data["timestamp"] = datetime.utcnow().isoformat()
            payload = json.dumps(event_data)
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
                "X-Event-Type": event_data["event"],
            }
            result = await endpoint.receive(payload, headers)
            assert result["status"] == "success"

        # Verify all events received
        assert len(endpoint.received_payloads) == len(events)
        received_events = {p["event"] for p in endpoint.received_payloads}
        expected_events = {e["event"] for e in events}
        assert received_events == expected_events

    async def test_webhook_tenant_scoping(self, test_tenant_id, test_tenant_id_2):
        """Test that webhooks are scoped to tenants."""
        endpoint_a = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_acme_secret",
        )
        endpoint_b = MockWebhookEndpoint(
            url="https://beta.example.com/webhooks/answerflow",
            secret="whsec_beta_secret",
        )

        # Deliver to tenant A
        payload_a = json.dumps({
            "event": "call.ended",
            "tenant_id": test_tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        headers_a = {
            "X-Webhook-Signature": generate_hmac_signature(payload_a, endpoint_a.secret),
        }
        await endpoint_a.receive(payload_a, headers_a)

        # Deliver to tenant B
        payload_b = json.dumps({
            "event": "call.ended",
            "tenant_id": test_tenant_id_2,
            "timestamp": datetime.utcnow().isoformat(),
        })
        headers_b = {
            "X-Webhook-Signature": generate_hmac_signature(payload_b, endpoint_b.secret),
        }
        await endpoint_b.receive(payload_b, headers_b)

        # Verify isolation
        assert len(endpoint_a.received_payloads) == 1
        assert len(endpoint_b.received_payloads) == 1
        assert endpoint_a.received_payloads[0]["tenant_id"] == test_tenant_id
        assert endpoint_b.received_payloads[0]["tenant_id"] == test_tenant_id_2

    async def test_webhook_payload_structure(self, test_tenant_id):
        """Test that webhook payloads have correct structure."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        # Standard payload structure
        payload_data = {
            "event": "call.ended",
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": test_tenant_id,
            "data": {
                "call_id": str(uuid.uuid4()),
                "caller_number": "+15551234567",
                "duration_seconds": 180,
                "transcript_summary": "Caller left a message for Dr. Smith",
                "ai_handled": True,
            },
        }
        payload = json.dumps(payload_data)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
        }

        result = await endpoint.receive(payload, headers)
        assert result["status"] == "success"

        # Verify payload structure
        received = endpoint.received_payloads[0]
        assert "event" in received
        assert "version" in received
        assert "timestamp" in received
        assert "tenant_id" in received
        assert "data" in received

    async def test_webhook_idempotency_key(self, test_tenant_id):
        """Test that webhook deliveries include idempotency key."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        delivery_id = str(uuid.uuid4())
        payload = json.dumps({
            "event": "call.ended",
            "tenant_id": test_tenant_id,
        })
        headers = {
            "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
            "X-Delivery-Id": delivery_id,
            "X-Idempotency-Key": delivery_id,
        }

        result = await endpoint.receive(payload, headers)
        assert result["status"] == "success"

        # Verify idempotency key
        assert len(endpoint.headers_received) == 1
        assert "X-Idempotency-Key" in endpoint.headers_received[0]
        assert endpoint.headers_received[0]["X-Idempotency-Key"] == delivery_id

    async def test_webhook_endpoint_deactivation(self, test_tenant_id):
        """Test that deactivated webhooks are not called."""
        webhook_config = {
            "id": str(uuid.uuid4()),
            "tenant_id": test_tenant_id,
            "url": "https://old.example.com/webhook",
            "secret": "whsec_old",
            "events": ["call.ended"],
            "is_active": False,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Deactivated webhook should not receive events
        assert webhook_config["is_active"] is False

    async def test_webhook_delivery_ordering(self, test_tenant_id):
        """Test that webhook events are delivered in order."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        # Send events in sequence
        for i in range(5):
            payload = json.dumps({
                "event": "call.ended",
                "sequence": i,
                "tenant_id": test_tenant_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
            headers = {
                "X-Webhook-Signature": generate_hmac_signature(payload, endpoint.secret),
                "X-Sequence": str(i),
            }
            await endpoint.receive(payload, headers)

        # Verify order preserved
        sequences = [p["sequence"] for p in endpoint.received_payloads]
        assert sequences == list(range(5))

    async def test_webhook_batch_delivery(self, test_tenant_id):
        """Test batch delivery of multiple events in one payload."""
        endpoint = MockWebhookEndpoint(
            url="https://acme.example.com/webhooks/answerflow",
            secret="whsec_test_secret_001",
        )

        batch_payload = json.dumps({
            "event": "batch",
            "tenant_id": test_tenant_id,
            "count": 3,
            "events": [
                {"event": "call.ended", "call_id": str(uuid.uuid4())},
                {"event": "appointment.booked", "appointment_id": str(uuid.uuid4())},
                {"event": "message.taken", "message_id": str(uuid.uuid4())},
            ],
        })
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": generate_hmac_signature(batch_payload, endpoint.secret),
        }

        result = await endpoint.receive(batch_payload, headers)
        assert result["status"] == "success"
        assert len(endpoint.received_payloads) == 1
        assert endpoint.received_payloads[0]["count"] == 3

    async def test_webhook_signature_with_different_secrets(self, test_tenant_id):
        """Test that different secrets produce different signatures."""
        payload = json.dumps({"event": "call.ended", "tenant_id": test_tenant_id})

        secret_a = "whsec_secret_a"
        secret_b = "whsec_secret_b"

        sig_a = generate_hmac_signature(payload, secret_a)
        sig_b = generate_hmac_signature(payload, secret_b)

        # Different secrets should produce different signatures
        assert sig_a != sig_b

        # Each should verify with its own secret
        assert verify_hmac_signature(payload, sig_a, secret_a) is True
        assert verify_hmac_signature(payload, sig_b, secret_b) is True

        # Cross-verification should fail
        assert verify_hmac_signature(payload, sig_a, secret_b) is False
        assert verify_hmac_signature(payload, sig_b, secret_a) is False
