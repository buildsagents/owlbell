# Owlbell API Design

## Base URL

Production: `https://owlbell.xyz/api`  
Local: `http://localhost:3000/api`

Auth: Supabase JWT in Authorization header (`Bearer <token>`) for authenticated endpoints.  
Unauthenticated endpoints (onboarding intake, Stripe webhook) use service-role API key.

---

## Onboarding

### POST /api/onboarding/intake

Submit onboarding data post-checkout.

**Request:**
```json
{
  "email": "owner@plumbing.com",
  "business_name": "Ace Plumbing",
  "owner_name": "John Smith",
  "mobile": "+447700900000",
  "payload": { ...OnboardingData }
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "status": "submitted"
}
```

---

### POST /api/onboarding/provision

Provision Retell assistant from completed onboarding data.

**Request:**
```json
{
  "step1_businessInfo": { "companyName": "Ace Plumbing", ... },
  "step2_businessDetails": { ... },
  "step7_aiVoice": { "voiceId": "79a125e8-...", "voiceName": "Morgan" }
}
```

**Response (200):**
```json
{
  "success": true,
  "assistantId": "retell-assistant-id",
  "message": "AI receptionist created successfully. Phone number provisioning requires manual configuration in the Retell dashboard."
}
```

**Errors:**
- `400` - missing required fields
- `503` - Retell not configured (server-side)
- `502` - Retell API failure

---

## Stripe

### POST /api/stripe/checkout

Create Stripe Checkout Session.

**Request:**
```json
{
  "planId": "pro",
  "email": "owner@plumbing.com",
  "successUrl": "https://owlbell.xyz/onboarding?session_id={CHECKOUT_SESSION_ID}"
}
```

**Response (200):**
```json
{
  "url": "https://checkout.stripe.com/..."
}
```

---

### POST /api/stripe/portal

Create Stripe Billing Portal session.

**Request:**
```json
{
  "customerId": "cus_xxx"
}
```

**Response (200):**
```json
{
  "url": "https://billing.stripe.com/..."
}
```

---

### POST /api/stripe/webhook

Stripe event webhook. Idempotency via `stripe-signature`.

**Events handled:**
- `checkout.session.completed` - creates org + profile + subscription
- `customer.subscription.updated` - syncs plan/status changes
- `customer.subscription.deleted` - marks subscription canceled

**Response (200):**
```json
{
  "received": true
}
```

---

## Voice

### POST /api/voice/webhook

Retell call webhook receiver.

**Request:** Retell webhook payload (call ended event)  

**Response (200):**
```json
{
  "ok": true
}
```

Stores call record in `calls` table via `parseCallWebhook()`.

---

## Frontend-facing (no auth)

### GET /api/demo

Demo call configuration for the demo page.

**Response (200):**
```json
{
  "retellPublicKey": "pk_xxx",
  "retellAssistantId": "assistant-id"
}
```

---

### POST /api/demo/web-call

Trigger a simulated demo call.

**Request:**
```json
{
  "phoneNumber": "+447700900000"
}
```

**Response (200):**
```json
{
  "success": true
}
```

---

## Dashboard (authenticated)

All dashboard endpoints require Supabase JWT auth.

### GET /api/dashboard/stats

**Response (200):**
```json
{
  "totalCalls": 142,
  "answerRate": 0.94,
  "appointmentsBooked": 38,
  "avgResponseSeconds": 3.2,
  "trend": "+12% vs last month"
}
```

### GET /api/dashboard/calls

Query params: `?page=1&limit=20&status=completed&search=smith`

**Response (200):**
```json
{
  "calls": [{ ...Call }],
  "total": 142,
  "page": 1,
  "totalPages": 8
}
```

### GET /api/dashboard/alerts

**Response (200):**
```json
{
  "alerts": [{ "type": "missed_call", "message": "...", "created_at": "..." }]
}
```

### GET /api/dashboard/agent

**Response (200):**
```json
{
  "id": "uuid",
  "status": "active",
  "greeting": "...",
  "voice_id": "...",
  "voice_name": "Morgan",
  "system_prompt": "...",
  "phone_number": "+447700900000",
  "updated_at": "..."
}
```

### PUT /api/dashboard/agent

Update agent settings.

**Request:**
```json
{
  "greeting": "Thanks for calling!...",
  "system_prompt": "You are...",
  "voice_id": "79a125e8-..."
}
```

**Response (200):**
```json
{
  "success": true
}
```

### GET /api/dashboard/subscription

**Response (200):**
```json
{
  "plan_tier": "pro",
  "status": "active",
  "current_period_end": "2026-07-28T00:00:00Z",
  "stripe_customer_id": "cus_xxx"
}
```

### GET /api/dashboard/settings

**Response (200):**
```json
{
  "opening_hours": "Mon-Fri 8:00-17:00",
  "emergency_available": true,
  "service_areas": "London, Manchester",
  "services_offered": ["Burst pipe repair", ...],
  "transfer_numbers": ["+447700900001"],
  "appointment_duration": 60,
  "buffer_time": 15,
  "calendar_provider": ""
}
```

### PUT /api/dashboard/settings

Update organization settings. Payload same shape as GET.

---

## Error Response Format

All errors return:
```json
{
  "error": "Human-readable message",
  "code": "ERROR_CODE"
}
```

HTTP status codes:
- `400` - validation error
- `401` - missing/invalid auth
- `403` - insufficient role
- `404` - resource not found
- `503` - upstream service unavailable (Retell, Stripe)
