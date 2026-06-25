# Owlbell API Reference

Complete reference for all 95+ REST API endpoints, WebSocket protocol, authentication, and error handling.

**Base URL**: `https://api.your-domain.com/api/v1`

---

## Table of Contents

- [Authentication](#authentication)
- [Response Format](#response-format)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)
- [Endpoints Reference](#endpoints-reference)
  - [Auth](#auth-endpoints)
  - [Tenants](#tenant-endpoints)
  - [Calls](#call-endpoints)
  - [Messages](#message-endpoints)
  - [Appointments](#appointment-endpoints)
  - [Knowledge Base](#knowledge-base-endpoints)
  - [Phone Numbers](#phone-number-endpoints)
  - [Call Routing](#call-routing-endpoints)
  - [Users](#user-endpoints)
  - [Analytics](#analytics-endpoints)
  - [Integrations](#integration-endpoints)
  - [System](#system-endpoints)
- [WebSocket Protocol](#websocket-protocol)

---

## Authentication

Owlbell uses **JWT (JSON Web Tokens)** for authentication. All API requests (except login and health check) must include a valid access token.

### Authentication Flow

```
Step 1: Login
--------------
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "your_password"
}

Response 200:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "admin@example.com",
    "full_name": "Admin User",
    "role": "super_admin"
  }
}

Step 2: Use Access Token
-------------------------
All subsequent requests include:
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

Step 3: Refresh Token
---------------------
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

Response 200:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

### Token Details

| Token Type | Expiration | Usage |
|------------|------------|-------|
| Access Token | 60 minutes | API requests |
| Refresh Token | 7 days | Obtain new access token |

### API Key Authentication

For service-to-service integration:

```
GET /api/v1/calls
X-API-Key: af_live_abc123xyz789...
```

API keys can be scoped to specific permissions and rate limits.

---

## Response Format

### Success Responses

All successful responses follow this envelope:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

For single resource responses, `meta` is omitted.

### Error Responses

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {"field": "email", "message": "Invalid email format"}
    ]
  }
}
```

---

## Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `VALIDATION_ERROR` | Request body validation failed |
| 400 | `BAD_REQUEST` | Generic bad request |
| 401 | `UNAUTHORIZED` | Missing or invalid token |
| 401 | `TOKEN_EXPIRED` | JWT token has expired |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 403 | `TENANT_ISOLATION` | Cross-tenant access attempt |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource already exists |
| 422 | `UNPROCESSABLE_ENTITY` | Business logic violation |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Dependency service down |

### Error Examples

```json
// 401 - Unauthorized
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required"
  }
}

// 403 - Forbidden
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "Manager role required for this operation"
  }
}

// 422 - Business logic error
{
  "success": false,
  "error": {
    "code": "UNPROCESSABLE_ENTITY",
    "message": "Time slot is no longer available"
  }
}
```

---

## Rate Limiting

Rate limits are applied per API key / user and per tenant.

| Tier | Requests/Minute | Requests/Hour | Concurrent |
|------|----------------|---------------|------------|
| Default | 60 | 3,000 | 10 |
| Pro | 300 | 15,000 | 50 |
| Enterprise | Unlimited | Unlimited | 200 |

### Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
X-RateLimit-Retry-After: 45
```

When exceeded:
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Retry-After: 60

{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Retry after 60 seconds."
  }
}
```

---

## Endpoints Reference

### Auth Endpoints

#### POST /auth/login
Authenticate and receive tokens.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response 200**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "full_name": "Jane Smith",
      "role": "tenant_admin",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440001"
    }
  }
}
```

**Errors**: 400 (validation), 401 (invalid credentials)

---

#### POST /auth/refresh
Refresh an expired access token.

**Request**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response 200**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
  }
}
```

---

#### POST /auth/logout
Invalidate the current refresh token.

**Headers**: `Authorization: Bearer <token>`

**Response 204**: No content

---

#### GET /auth/me
Get current authenticated user.

**Response 200**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "full_name": "Jane Smith",
    "role": "tenant_admin",
    "tenant": {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Smith Dental",
      "slug": "smith-dental"
    },
    "permissions": ["calls.read", "calls.write", "messages.read", ...]
  }
}
```

---

#### POST /auth/change-password
Change the authenticated user's password.

**Request**:
```json
{
  "current_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response 200**:
```json
{
  "success": true,
  "data": { "message": "Password updated successfully" }
}
```

---

### Tenant Endpoints

#### GET /tenants
List all tenants (super_admin only).

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `per_page` | integer | Items per page (default: 20, max: 100) |
| `search` | string | Search by name or slug |
| `is_active` | boolean | Filter by status |

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Smith Dental",
      "slug": "smith-dental",
      "phone_number": "+15551234567",
      "timezone": "America/New_York",
      "is_active": true,
      "user_count": 3,
      "call_count_today": 12,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

---

#### POST /tenants
Create a new tenant.

**Request**:
```json
{
  "name": "Johnson Law Office",
  "slug": "johnson-law",
  "phone_number": "+15559876543",
  "timezone": "America/Chicago",
  "language": "en-US",
  "greeting": "Thank you for calling Johnson Law Office. How may I assist you?",
  "business_hours": {
    "monday": {"open": "08:00", "close": "17:00", "closed": false},
    "tuesday": {"open": "08:00", "close": "17:00", "closed": false},
    "wednesday": {"open": "08:00", "close": "17:00", "closed": false},
    "thursday": {"open": "08:00", "close": "17:00", "closed": false},
    "friday": {"open": "08:00", "close": "16:00", "closed": false},
    "saturday": {"closed": true},
    "sunday": {"closed": true}
  }
}
```

**Response 201**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "name": "Johnson Law Office",
    "slug": "johnson-law",
    ...
  }
}
```

---

#### GET /tenants/{tenant_id}
Get a single tenant.

**Response 200**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "Smith Dental",
    "slug": "smith-dental",
    "phone_number": "+15551234567",
    "timezone": "America/New_York",
    "language": "en-US",
    "greeting": "Thank you for calling Smith Dental...",
    "business_hours": { ... },
    "ai_config": {
      "voice": "en_US-lessac-medium",
      "speaking_rate": 1.1,
      "temperature": 0.7,
      "max_response_length": 150,
      "personality": "friendly"
    },
    "is_active": true,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-20T14:30:00Z"
  }
}
```

---

#### PUT /tenants/{tenant_id}
Update tenant configuration.

**Request**: Same fields as POST (all optional)

**Response 200**: Updated tenant object

---

#### PATCH /tenants/{tenant_id}/ai-config
Update AI-specific configuration.

**Request**:
```json
{
  "voice": "en_US-lessac-medium",
  "speaking_rate": 1.2,
  "temperature": 0.6,
  "max_response_length": 120,
  "personality": "professional",
  "system_prompt": "You are the AI receptionist for {business_name}. You are friendly, efficient, and helpful."
}
```

**Response 200**: Updated AI config

---

### Call Endpoints

#### GET /calls
List calls for the current tenant.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number |
| `per_page` | integer | Items per page |
| `status` | string | Filter: `connected`, `ended`, `missed` |
| `direction` | string | Filter: `inbound`, `outbound` |
| `date_from` | ISO datetime | Start date filter |
| `date_to` | ISO datetime | End date filter |
| `phone` | string | Filter by caller phone (partial match) |
| `search` | string | Search in transcriptions |
| `sort` | string | Sort field, prefix `-` for desc |

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440010",
      "phone_number": "+15551112222",
      "caller_id": "John Doe",
      "direction": "inbound",
      "status": "ended",
      "duration_seconds": 145,
      "transcription": "I'd like to schedule a cleaning...",
      "transcription_full": [{"speaker": "caller", "text": "...", "timestamp": "..."}],
      "sentiment_score": 0.72,
      "recording_available": true,
      "outcome": "appointment_booked",
      "created_at": "2024-01-20T09:15:00Z",
      "ended_at": "2024-01-20T09:17:25Z"
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 150 }
}
```

---

#### GET /calls/{call_id}
Get detailed call information.

**Response 200**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440010",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
    "phone_number": "+15551112222",
    "caller_id": "John Doe",
    "direction": "inbound",
    "status": "ended",
    "duration_seconds": 145,
    "transcription": "I'd like to schedule a cleaning...",
    "transcription_full": [
      {"speaker": "ai", "text": "Thank you for calling Smith Dental...", "timestamp": "2024-01-20T09:15:05Z", "latency_ms": 1200},
      {"speaker": "caller", "text": "Hi, I'd like to schedule a cleaning.", "timestamp": "2024-01-20T09:15:15Z"},
      {"speaker": "ai", "text": "I'd be happy to help...", "timestamp": "2024-01-20T09:15:18Z", "latency_ms": 2800},
      ...
    ],
    "sentiment_score": 0.72,
    "sentiment_label": "positive",
    "recording_url": "https://api.your-domain.com/recordings/550e8400-...",
    "recording_duration": 145,
    "outcome": "appointment_booked",
    "actions_taken": ["checked_availability", "booked_appointment", "sent_confirmation"],
    "metadata": {"sip_call_id": "abc123@192.168.1.1", "codec": "opus"},
    "created_at": "2024-01-20T09:15:00Z",
    "answered_at": "2024-01-20T09:15:03Z",
    "ended_at": "2024-01-20T09:17:25Z"
  }
}
```

---

#### GET /calls/{call_id}/recording
Download call recording (audio file).

**Response**: `audio/wav` file download

**Headers**:
```http
Content-Type: audio/wav
Content-Disposition: attachment; filename="call_2024-01-20_091500.wav"
Content-Length: 2892400
```

---

#### GET /calls/active
Get currently active calls (real-time).

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440020",
      "phone_number": "+15553334444",
      "caller_id": "Jane Wilson",
      "status": "connected",
      "duration_seconds": 45,
      "current_state": "speaking",
      "transcription_so_far": "I'm having a toothache...",
      "ai_speaking": false,
      "created_at": "2024-01-20T10:00:00Z"
    }
  ],
  "meta": { "total": 1 }
}
```

---

#### POST /calls/{call_id}/transfer
Transfer an active call to a human.

**Request**:
```json
{
  "destination": "+15551234999",
  "reason": "Customer requested human agent"
}
```

**Response 200**:
```json
{
  "success": true,
  "data": {
    "call_id": "550e8400-e29b-41d4-a716-446655440020",
    "status": "transferring",
    "destination": "+15551234999"
  }
}
```

---

#### POST /calls/{call_id}/hangup
Forcefully end a call.

**Response 200**:
```json
{
  "success": true,
  "data": { "status": "ended", "hangup_cause": "api_request" }
}
```

---

### Message Endpoints

#### GET /messages
List messages for the tenant.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `page`, `per_page` | integer | Pagination |
| `urgency` | string | Filter: `low`, `medium`, `high` |
| `is_read` | boolean | Read status filter |
| `date_from`, `date_to` | ISO datetime | Date range |
| `phone` | string | Filter by caller phone |
| `search` | string | Search in content |

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440030",
      "call_id": "550e8400-e29b-41d4-a716-446655440031",
      "caller_name": "Robert Brown",
      "caller_phone": "+15557778888",
      "content": "Please call me back about my insurance claim. Reference #12345.",
      "urgency": "high",
      "is_read": false,
      "notified": true,
      "notification_sent_at": "2024-01-20T11:00:05Z",
      "created_at": "2024-01-20T11:00:00Z"
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 45 }
}
```

---

#### GET /messages/{message_id}
Get a single message.

**Response 200**: Full message object with call context

---

#### PATCH /messages/{message_id}
Update message (mark as read, change urgency).

**Request**:
```json
{
  "is_read": true,
  "notes": "Called back at 2pm. Issue resolved."
}
```

**Response 200**: Updated message

---

#### DELETE /messages/{message_id}
Delete a message.

**Response 204**: No content

---

#### POST /messages/{message_id}/callback
Initiate a callback to the message caller.

**Request**:
```json
{
  "from_number": "+15551234567",
  "note": "Returning your call about insurance"
}
```

**Response 202**: Accepted (async processing)

---

### Appointment Endpoints

#### GET /appointments
List appointments.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `page`, `per_page` | integer | Pagination |
| `status` | string | `scheduled`, `completed`, `cancelled`, `no_show` |
| `date_from`, `date_to` | ISO datetime | Date range |
| `attendee_phone` | string | Filter by phone |

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440040",
      "google_event_id": "abc123@google.com",
      "title": "Dental Cleaning - John Smith",
      "description": "Regular 6-month cleaning. Booked via AI.",
      "start_time": "2024-01-22T14:00:00Z",
      "end_time": "2024-01-22T14:30:00Z",
      "attendee_name": "John Smith",
      "attendee_phone": "+15551112222",
      "attendee_email": "john@example.com",
      "status": "scheduled",
      "source": "ai_agent",
      "created_at": "2024-01-20T09:17:00Z"
    }
  ]
}
```

---

#### POST /appointments
Create an appointment manually.

**Request**:
```json
{
  "title": "Consultation - Jane Doe",
  "start_time": "2024-01-23T10:00:00Z",
  "end_time": "2024-01-23T10:30:00Z",
  "attendee_name": "Jane Doe",
  "attendee_phone": "+15553334444",
  "attendee_email": "jane@example.com",
  "description": "Initial consultation"
}
```

**Response 201**: Created appointment

---

#### GET /appointments/{appointment_id}
Get appointment details.

---

#### PUT /appointments/{appointment_id}
Update an appointment.

---

#### DELETE /appointments/{appointment_id}
Cancel an appointment (updates Google Calendar).

**Response 200**: Cancelled appointment

---

#### GET /appointments/availability
Check available time slots.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | ISO date | Yes | Date to check |
| `duration` | integer | No | Duration in minutes (default: 30) |

**Response 200**:
```json
{
  "success": true,
  "data": {
    "date": "2024-01-22",
    "timezone": "America/New_York",
    "available_slots": [
      {"start": "08:00", "end": "08:30"},
      {"start": "09:00", "end": "09:30"},
      {"start": "10:00", "end": "10:30"},
      {"start": "14:00", "end": "14:30"},
      {"start": "15:00", "end": "15:30"}
    ],
    "busy_slots": [
      {"start": "11:00", "end": "12:00", "title": "Staff Meeting"}
    ]
  }
}
```

---

### Knowledge Base Endpoints

#### GET /knowledge/documents
List uploaded documents.

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440050",
      "filename": "services-pricing.pdf",
      "file_size": 245760,
      "mime_type": "application/pdf",
      "chunk_count": 15,
      "is_active": true,
      "created_at": "2024-01-18T10:00:00Z"
    }
  ]
}
```

---

#### POST /knowledge/documents
Upload a document.

**Content-Type**: `multipart/form-data`

**Request Body**:
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | PDF, DOCX, or TXT file (max 50MB) |
| `is_active` | boolean | Whether to use in AI context |

**Response 201**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440051",
    "filename": "faq-document.pdf",
    "chunk_count": 23,
    "status": "processing",
    "processing_job_id": "job_abc123"
  }
}
```

---

#### GET /knowledge/documents/{doc_id}
Get document details.

---

#### DELETE /knowledge/documents/{doc_id}
Delete a document and its chunks.

**Response 204**: No content

---

#### PATCH /knowledge/documents/{doc_id}
Update document (activate/deactivate).

**Request**:
```json
{
  "is_active": false
}
```

---

#### POST /knowledge/search
Search the knowledge base.

**Request**:
```json
{
  "query": "What are your hours on Saturday?",
  "top_k": 5
}
```

**Response 200**:
```json
{
  "success": true,
  "data": {
    "query": "What are your hours on Saturday?",
    "results": [
      {
        "chunk_id": "550e8400-e29b-41d4-a716-446655440060",
        "document_id": "550e8400-e29b-41d4-a716-446655440050",
        "document_name": "services-pricing.pdf",
        "content": "Our office hours are Monday-Friday 8am-5pm. We are closed on weekends.",
        "score": 0.92,
        "position": 1
      }
    ]
  }
}
```

---

#### POST /knowledge/test
Test AI response with knowledge base.

**Request**:
```json
{
  "query": "Do you accept walk-ins?"
}
```

**Response 200**:
```json
{
  "success": true,
  "data": {
    "query": "Do you accept walk-ins?",
    "response": "Yes, we do accept walk-ins for minor issues...",
    "sources": [
      {"document": "faq-document.pdf", "chunk": "Walk-in policy...", "score": 0.88}
    ],
    "latency_ms": 1200
  }
}
```

---

### Phone Number Endpoints

#### GET /phone-numbers
List configured phone numbers.

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440070",
      "phone_number": "+15551234567",
      "provider": "telnyx",
      "provider_config": {"sip_trunk": "telnyx", "auth_username": "..."},
      "route_to": "ai_agent",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
      "is_active": true,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

---

#### POST /phone-numbers
Add a phone number.

**Request**:
```json
{
  "phone_number": "+15559876543",
  "provider": "telnyx",
  "provider_config": {
    "auth_username": "user",
    "auth_password": "pass"
  },
  "route_to": "ai_agent",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Response 201**: Created phone number

---

#### DELETE /phone-numbers/{number_id}
Remove a phone number.

---

### Call Routing Endpoints

#### GET /routing/rules
List routing rules.

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440080",
      "name": "Emergency Routing",
      "priority": 1,
      "condition": {
        "type": "keyword_match",
        "keywords": ["emergency", "urgent", "pain", "bleeding"],
        "match_any": true
      },
      "action": {
        "type": "forward",
        "destination": "+15551234999",
        "timeout": 30,
        "fallback": "take_message_high_priority"
      },
      "is_active": true
    }
  ]
}
```

---

#### POST /routing/rules
Create a routing rule.

**Request**:
```json
{
  "name": "After Hours Message",
  "priority": 10,
  "condition": {
    "type": "time_based",
    "business_hours": false
  },
  "action": {
    "type": "ai_greeting",
    "greeting": "You've reached us after hours. I can take a message or help book an appointment."
  }
}
```

**Response 201**: Created rule

---

#### PUT /routing/rules/{rule_id}
Update a routing rule.

---

#### DELETE /routing/rules/{rule_id}
Delete a routing rule.

---

### User Endpoints

#### GET /users
List users (tenant-scoped or system-wide).

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `tenant_id` | UUID | Filter by tenant |
| `role` | string | Filter by role |
| `is_active` | boolean | Filter by status |

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440090",
      "email": "manager@smithdental.com",
      "full_name": "Sarah Manager",
      "role": "manager",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
      "is_active": true,
      "last_login": "2024-01-20T08:00:00Z",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

---

#### POST /users
Create a new user.

**Request**:
```json
{
  "email": "newuser@example.com",
  "full_name": "New User",
  "password": "temp_password_change_me",
  "role": "agent",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Response 201**: Created user (password not returned)

---

#### GET /users/{user_id}
Get user details.

---

#### PUT /users/{user_id}
Update user.

---

#### DELETE /users/{user_id}
Deactivate (soft-delete) a user.

---

### Analytics Endpoints

#### GET /analytics/calls
Call analytics summary.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `date_from` | ISO date | Start date |
| `date_to` | ISO date | End date |
| `group_by` | string | `day`, `week`, `month` |

**Response 200**:
```json
{
  "success": true,
  "data": {
    "period": {"from": "2024-01-01", "to": "2024-01-31"},
    "summary": {
      "total_calls": 450,
      "answered_calls": 412,
      "missed_calls": 38,
      "average_duration": 145,
      "total_minutes": 1825,
      "appointments_booked": 67,
      "messages_taken": 89
    },
    "by_day": [
      {"date": "2024-01-20", "calls": 18, "avg_duration": 132, "missed": 2},
      ...
    ],
    "by_hour": [
      {"hour": 9, "calls": 45},
      {"hour": 10, "calls": 62},
      {"hour": 11, "calls": 58},
      ...
    ],
    "top_callers": [
      {"phone": "+15551112222", "calls": 5, "total_duration": 450}
    ],
    "outcomes": {
      "appointment_booked": 67,
      "message_taken": 89,
      "call_routed": 23,
      "faq_answered": 233
    }
  }
}
```

---

#### GET /analytics/messages
Message analytics.

---

#### GET /analytics/appointments
Appointment analytics.

---

#### GET /dashboard
Get dashboard summary (aggregated stats).

**Response 200**:
```json
{
  "success": true,
  "data": {
    "today": {
      "calls": 12,
      "active_calls": 1,
      "messages": 3,
      "appointments": 2,
      "avg_duration": 120
    },
    "this_week": {
      "calls": 78,
      "messages": 18,
      "appointments": 14
    },
    "system_health": {
      "status": "healthy",
      "ai_response_avg_ms": 2100,
      "freeswitch_status": "connected",
      "ollama_status": "ready"
    },
    "recent_activity": [
      {"type": "call.ended", "call_id": "...", "duration": 145, "timestamp": "..."},
      {"type": "message.received", "message_id": "...", "urgency": "high", "timestamp": "..."}
    ]
  }
}
```

---

### Integration Endpoints

#### GET /integrations
List available integrations.

**Response 200**:
```json
{
  "success": true,
  "data": [
    {
      "id": "google_calendar",
      "name": "Google Calendar",
      "description": "Two-way calendar sync",
      "is_connected": true,
      "configured_at": "2024-01-16T10:00:00Z"
    },
    {
      "id": "smtp",
      "name": "Email (SMTP)",
      "description": "Send email notifications",
      "is_connected": true
    },
    {
      "id": "twilio_sms",
      "name": "Twilio SMS",
      "description": "Send SMS notifications",
      "is_connected": false
    }
  ]
}
```

---

#### POST /integrations/google-calendar/connect
Initiate Google Calendar OAuth flow.

**Response 200**:
```json
{
  "success": true,
  "data": {
    "auth_url": "https://accounts.google.com/o/oauth2/auth?client_id=...&redirect_uri=...&scope=..."
  }
}
```

---

#### POST /integrations/google-calendar/callback
OAuth callback handler.

**Request**:
```json
{
  "code": "4/0Adeu...",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

---

#### DELETE /integrations/google-calendar/disconnect
Disconnect Google Calendar.

---

#### POST /integrations/smtp/configure
Configure SMTP settings.

**Request**:
```json
{
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "app-specific-password",
  "from_address": "noreply@your-domain.com",
  "use_tls": true
}
```

---

#### POST /integrations/twilio/configure
Configure Twilio SMS.

**Request**:
```json
{
  "account_sid": "AC...",
  "auth_token": "...",
  "phone_number": "+15551234567"
}
```

---

#### POST /webhooks
Register a webhook endpoint.

**Request**:
```json
{
  "url": "https://your-app.com/webhooks/answerflow",
  "events": ["call.ended", "message.received", "appointment.created"],
  "secret": "webhook_signing_secret",
  "is_active": true
}
```

**Response 201**: Created webhook with `id` and `signing_secret`

---

#### DELETE /webhooks/{webhook_id}
Remove a webhook.

---

### System Endpoints

#### GET /health
Health check (no auth required).

**Response 200**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "0.1.0",
    "timestamp": "2024-01-20T12:00:00Z",
    "services": {
      "database": "ok",
      "redis": "ok",
      "freeswitch": "ok",
      "ollama": "ok",
      "piper": "ok"
    },
    "uptime_seconds": 86400
  }
}
```

---

#### GET /health/detailed
Detailed health with diagnostics (auth required).

**Response 200**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "services": {
      "database": {"status": "ok", "latency_ms": 2, "connections_active": 5},
      "redis": {"status": "ok", "latency_ms": 1, "memory_used_mb": 45},
      "freeswitch": {"status": "ok", "version": "1.10.11", "active_calls": 1},
      "ollama": {"status": "ok", "model": "llama3.2:3b", "gpu": false},
      "piper": {"status": "ok", "voices_loaded": 3}
    },
    "resources": {
      "cpu_percent": 45,
      "memory_percent": 62,
      "disk_percent": 34
    },
    "ai_performance": {
      "avg_stt_latency_ms": 1200,
      "avg_llm_latency_ms": 2800,
      "avg_tts_latency_ms": 300
    }
  }
}
```

---

#### GET /system/status
System status page data.

---

#### POST /system/ai/test
Test AI pipeline end-to-end.

**Request**:
```json
{
  "text": "Hello, I'd like to book an appointment for tomorrow."
}
```

**Response 200**:
```json
{
  "success": true,
  "data": {
    "input_text": "Hello, I'd like to book an appointment for tomorrow.",
    "llm_response": "I'd be happy to help you schedule an appointment for tomorrow...",
    "tts_generated": true,
    "tts_audio_url": "/tmp/test_tts_abc123.wav",
    "latencies": {
      "llm_ms": 1850,
      "tts_ms": 220,
      "total_ms": 2070
    }
  }
}
```

---

## WebSocket Protocol

### Connection

```
URL: wss://ws.your-domain.com/api/v1/ws/live

Authentication (choose one):
  1. Query parameter: ?token=eyJhbGci...
  2. Protocol header: Sec-WebSocket-Protocol: eyJhbGci...
```

### Message Format

All WebSocket messages are JSON:

```json
{
  "type": "message_type",
  "id": "client-generated-id",
  "timestamp": "2024-01-20T12:00:00Z",
  "data": { ... }
}
```

### Client-to-Server Messages

#### Subscribe to channels

```json
{
  "type": "subscribe",
  "id": "sub-1",
  "data": {
    "channels": ["calls", "messages", "appointments", "system"]
  }
}
```

**Response**:
```json
{
  "type": "subscribed",
  "id": "sub-1",
  "data": {
    "channels": ["calls", "messages", "appointments", "system"]
  }
}
```

---

#### Unsubscribe from channels

```json
{
  "type": "unsubscribe",
  "id": "unsub-1",
  "data": {
    "channels": ["system"]
  }
}
```

---

#### Ping (keep-alive)

```json
{"type": "ping", "id": "ping-1"}
```

**Response**:
```json
{"type": "pong", "id": "ping-1", "timestamp": "2024-01-20T12:00:01Z"}
```

### Server-to-Client Events

#### call.started
A new call has been received.

```json
{
  "type": "call.started",
  "timestamp": "2024-01-20T12:00:00Z",
  "data": {
    "call_id": "550e8400-e29b-41d4-a716-446655440100",
    "phone_number": "+15551112222",
    "caller_id": "John Doe",
    "direction": "inbound",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
    "started_at": "2024-01-20T12:00:00Z"
  }
}
```

---

#### call.updated
Call state has changed (e.g., AI speaking, listening).

```json
{
  "type": "call.updated",
  "timestamp": "2024-01-20T12:00:15Z",
  "data": {
    "call_id": "550e8400-e29b-41d4-a716-446655440100",
    "state": "speaking",
    "duration_seconds": 15,
    "transcription_so_far": "I'd like to schedule..."
  }
}
```

---

#### call.ended
A call has ended.

```json
{
  "type": "call.ended",
  "timestamp": "2024-01-20T12:02:30Z",
  "data": {
    "call_id": "550e8400-e29b-41d4-a716-446655440100",
    "duration_seconds": 150,
    "outcome": "appointment_booked",
    "transcription": "I'd like to schedule a cleaning...",
    "sentiment_score": 0.75,
    "recording_available": true
  }
}
```

---

#### message.received
A new message was taken.

```json
{
  "type": "message.received",
  "timestamp": "2024-01-20T12:05:00Z",
  "data": {
    "message_id": "550e8400-e29b-41d4-a716-446655440110",
    "call_id": "550e8400-e29b-41d4-a716-446655440111",
    "caller_name": "Jane Smith",
    "caller_phone": "+15553334444",
    "content": "Please call me back about pricing.",
    "urgency": "medium",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

---

#### appointment.created
An appointment was booked.

```json
{
  "type": "appointment.created",
  "timestamp": "2024-01-20T12:10:00Z",
  "data": {
    "appointment_id": "550e8400-e29b-41d4-a716-446655440120",
    "title": "Dental Cleaning - John Doe",
    "start_time": "2024-01-22T14:00:00Z",
    "attendee_name": "John Doe",
    "attendee_phone": "+15551112222"
  }
}
```

---

#### system.notification
System-level notification.

```json
{
  "type": "system.notification",
  "timestamp": "2024-01-20T12:00:00Z",
  "data": {
    "level": "warning",
    "title": "High CPU Usage",
    "message": "CPU usage is at 85% for the last 5 minutes.",
    "details": {"cpu_percent": 85, "duration_minutes": 5}
  }
}
```

Levels: `info`, `warning`, `error`, `critical`

---

### JavaScript Client Example

```javascript
const ws = new WebSocket(
  'wss://ws.your-domain.com/api/v1/ws/live?token=YOUR_JWT_TOKEN'
);

ws.onopen = () => {
  console.log('Connected to Owlbell');
  
  // Subscribe to channels
  ws.send(JSON.stringify({
    type: 'subscribe',
    id: 'sub-1',
    data: { channels: ['calls', 'messages'] }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  switch (msg.type) {
    case 'call.started':
      showNotification(`Incoming call from ${msg.data.caller_id}`);
      addCallToDashboard(msg.data);
      break;
      
    case 'call.ended':
      updateCallStats(msg.data);
      if (msg.data.recording_available) {
        addRecordingPlayer(msg.data.call_id);
      }
      break;
      
    case 'message.received':
      if (msg.data.urgency === 'high') {
        showUrgentAlert(msg.data);
      }
      addMessageToInbox(msg.data);
      break;
      
    case 'pong':
      // Keep-alive acknowledged
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected. Reconnecting in 5s...');
  setTimeout(() => connect(), 5000);
};

// Send heartbeat every 30 seconds
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping', id: `ping-${Date.now()}` }));
  }
}, 30000);
```

---

## SDK Examples

### Python

```python
import requests

BASE_URL = "https://api.your-domain.com/api/v1"
TOKEN = "your_jwt_token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# List recent calls
response = requests.get(f"{BASE_URL}/calls?page=1&per_page=10", headers=headers)
calls = response.json()["data"]

for call in calls:
    print(f"{call['phone_number']}: {call['duration_seconds']}s")

# Get today's analytics
from datetime import date
today = date.today().isoformat()
response = requests.get(
    f"{BASE_URL}/analytics/calls?date_from={today}&date_to={today}",
    headers=headers
)
print(f"Today's calls: {response.json()['data']['summary']['total_calls']}")
```

### cURL

```bash
# Login
curl -X POST https://api.your-domain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your_password"}'

# List calls
curl https://api.your-domain.com/api/v1/calls \
  -H "Authorization: Bearer YOUR_TOKEN"

# Mark message as read
curl -X PATCH https://api.your-domain.com/api/v1/messages/UUID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_read":true}'

# Check availability
curl "https://api.your-domain.com/api/v1/appointments/availability?date=2024-01-22" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture
- [DEPLOYMENT.md](DEPLOYMENT.md) -- Production deployment
- [DEVELOPMENT.md](DEVELOPMENT.md) -- Contributing and development
- [SECURITY.md](SECURITY.md) -- Authentication and security details
