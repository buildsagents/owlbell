# Owlbell System Architecture

This document describes the complete architecture of Owlbell, including design decisions, data flows, component interactions, and scaling strategies.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagrams](#architecture-diagrams)
- [Data Flow: Inbound Call](#data-flow-inbound-call)
- [Component Descriptions](#component-descriptions)
- [Technology Choices](#technology-choices)
- [Multi-Tenancy Design](#multi-tenancy-design)
- [Security Architecture](#security-architecture)
- [Database Schema Overview](#database-schema-overview)
- [API Design](#api-design)
- [Scaling Strategy](#scaling-strategy)
- [Disaster Recovery](#disaster-recovery)

---

## System Overview

Owlbell is a distributed system composed of 9 subsystems working together to provide an AI-powered phone answering service. The system follows a modular, microservices-inspired architecture using Docker Compose for deployment.

### Design Principles

1. **Privacy-First**: All AI processing happens locally. No audio, transcripts, or conversation data ever leaves the server.
2. **Zero-Budget Friendly**: Runs on free-tier cloud resources or inexpensive VPS. No mandatory paid APIs.
3. **Modular**: Each subsystem can be replaced or upgraded independently.
4. **Multi-Tenant**: Single installation serves multiple businesses with full data isolation.
5. **Observable**: Comprehensive logging, metrics, and tracing throughout.

### High-Level Architecture

```
                    +-------------------------+
                    |    PSTN / SIP Network   |
                    |  (Phone Numbers)        |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   FreeSWITCH PBX        |
                    |   (SIP + Media)         |
                    +------------+------------+
                                 |
              +------------------+------------------+
              |                                     |
   +----------v----------+             +----------v----------+
   |   ESL Event Socket  |             |   RTP Media Stream  |
   |   (Call Control)    |             |   (Audio I/O)       |
   +----------+----------+             +----------+----------+
              |                                     |
   +----------v----------+             +----------v----------+
   |   Telephony Engine  |             |   Audio Pipeline    |
   |   (Python Service)  |<----------->|   (Chunk/Encode)    |
   +----------+----------+             +----------+----------+
              |                                     |
              +------------------+------------------+
                                 |
                    +------------v------------+
                    |   AI Pipeline Service   |
                    |   (STT --> LLM --> TTS) |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   Orchestration Layer   |
                    |   (FastAPI + Celery)    |
                    +------------+------------+
                                 |
              +------------------+------------------+
              |                  |                  |
   +----------v----------+ +-----v------+ +--------v---------+
   |   Business Logic    | |  Integrations | |   Database      |
   |   (Messages, Appts) | |  (Calendar,   | |   (PostgreSQL)  |
   |                     | |   CRM, SMS)   | |                 |
   +----------+----------+ +-----+--------+ +--------+--------+
              |                  |                   |
              +------------------+-------------------+
                                 |
                    +------------v------------+
                    |   Client Applications   |
                    |   (React Dashboard)     |
                    +-------------------------+
```

---

## Architecture Diagrams

### 1. Deployment Architecture

```
    +----------------------------------+
    |           Host Server            |
    |  (Oracle Cloud / Hetzner / ...)  |
    |                                  |
    |  +----------------------------+  |
    |  |      Docker Network        |  |
    |  |     (answerflow-net)       |  |
    |  |                            |  |
    |  |  +---------------------+   |  |
    |  |  | nginx (reverse proxy)|   |  |
    |  |  | :80, :443           |   |  |
    |  |  +--+-----+-----+------+   |  |
    |  |     |     |     |          |  |
    |  |  +--v--+ +v---+ +v---+    |  |
    |  |  | API | |FE  | |WS  |    |  |
    |  |  | :8000|:3000|:8765|    |  |
    |  |  +--+--+ +----+ +----+    |  |
    |  |     |                     |  |
    |  |  +--v------------------+   |  |
    |  |  |  PostgreSQL :5432    |   |  |
    |  |  +---------------------+   |  |
    |  |                            |  |
    |  |  +---------------------+   |  |
    |  |  |  Redis :6379         |   |  |
    |  |  +---------------------+   |  |
    |  |                            |  |
    |  |  +---------------------+   |  |
    |  |  |  FreeSWITCH         |   |  |
    |  |  |  :5060/udp/tcp      |   |  |
    |  |  |  :8021 (ESL)        |   |  |
    |  |  |  :10000-20000/udp   |   |  |
    |  |  +---------------------+   |  |
    |  |                            |  |
    |  |  +---------------------+   |  |
    |  |  |  Ollama :11434      |   |  |
    |  |  +---------------------+   |  |
    |  |                            |  |
    |  |  +---------------------+   |  |
    |  |  |  Piper TTS :5000    |   |  |
    |  |  +---------------------+   |  |
    |  |                            |  |
    |  |  +---------------------+   |  |
    |  |  |  Prometheus:9090    |   |  |
    |  |  |  Grafana:3001       |   |  |
    |  |  +---------------------+   |  |
    |  |                            |  |
    |  +----------------------------+  |
    |                                  |
    +----------------------------------+
```

### 2. AI Pipeline Architecture

```
  +----------+     +-----------+     +-----------+     +-----------+     +----------+
  |  Raw     |     |  Audio    |     |  Speech   |     |  Language |     |  Synthesized |
  |  Audio   | --> |  Pre-     | --> |  to       | --> |  Model    | --> |  Speech      |
  |  (RTP)   |     |  process  |     |  Text     |     |  (LLM)    |     |  (Audio)     |
  +----------+     +-----------+     +-----------+     +-----------+     +----------+
       |                |                 |                 |                 |
       |  8k/16k PCM    |  Resample      |   Text prompt   |   Text response |  8k PCM
       |  G.711/Opus    |  Normalize     |   + System      |   + Emotion     |  G.711
       |                |  VAD detect    |   + Context     |   markers       |
       |                |                |   + History     |                 |
       |                |                |                 |                 |
  FreeSWITCH        Python           Whisper           Ollama             Piper
  media stack       asyncio          (faster-          (llama3.2)         (onnxruntime)
                    buffers          whisper)

  Latency targets:
  - Audio capture:    < 50ms
  - Pre-processing:   < 100ms
  - STT (Whisper):    500ms - 2000ms
  - LLM inference:    1000ms - 4000ms
  - TTS (Piper):      100ms - 500ms
  - Audio playback:   < 50ms
  ====================================
  Total end-to-end:   1750ms - 6650ms
  (GPU reduces total to ~1000ms - 2500ms)
```

### 3. Call State Machine

```
                           +-----------+
                           |  IDLE     |
                           | (waiting) |
                           +-----+-----+
                                 |
                    +------------v------------+
                    |   INCOMING_CALL         |
                    |   (ringing, ESL        |
                    |    CHANNEL_CREATE)      |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   GREETING              |
                    |   (play welcome,       |
                    |    TTS greeting)        |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   LISTENING             |
                    |   (VAD active,          |
                    |    recording audio)     |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   PROCESSING            |
                    |   (STT -> LLM -> TTS)   |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   SPEAKING              |
                    |   (playing TTS audio)   |
                    +------------+------------+
                                 |
                    +------------+------------+
                    |                         |
       +------------v------------+  +---------v---------+
       |   RETURN_TO_LISTENING   |  |   CALL_END        |
       |   (more conversation)   |  |   (hangup,        |
       +-------------------------+  |    transfer,      |
                                    |    timeout)       |
                                    +-------------------+
```

---

## Data Flow: Inbound Call

This section traces a complete inbound call through every subsystem.

### Step-by-Step Flow

```
Step 1: Call Arrives
====================
Caller --> PSTN --> SIP Trunk Provider --> Internet --> Server:5060
                                                         (FreeSWITCH)

Step 2: SIP Negotiation
========================
FreeSWITCH Sofia Module:
  - Receives INVITE
  - Authenticates (if required)
  - Negotiates codecs (Opus/PCMU preferred)
  - Responds 200 OK
  - Establishes RTP session on port 10000-20000

Step 3: ESL Event Notification
===============================
FreeSWITCH ESL (Event Socket Layer):
  - Emits CHANNEL_CREATE event
  - Telephony Engine (Python) receives event
  - Creates CallSession object
  - Associates with tenant via dialed number

Step 4: Play Greeting
======================
Telephony Engine:
  - Generates greeting text ("Thank you for calling...")
  - Sends to Piper TTS service
  - Receives WAV audio
  - Instructs FreeSWITCH to play audio via mod_dptools
  - Caller hears: "Thank you for calling Smith Dental..."

Step 5: Listen for Speech
==========================
Telephony Engine:
  - Activates VAD (Voice Activity Detection)
  - Instructs FreeSWITCH to start recording
  - Audio chunks stream via ESL
  - Buffers accumulate in memory ring buffer

Step 6: Speech-to-Text
=======================
When VAD detects speech end (silence > 800ms):
  - Buffer flushed to Whisper STT
  - Whisper transcribes to text
  - Result: "I'd like to book an appointment"

Step 7: Intent Recognition + LLM
=================================
Telephony Engine:
  - Sends text + conversation history + context to Ollama
  - Ollama runs llama3.2:3b with system prompt
  - LLM decides intent: "book_appointment"
  - LLM generates response: "I'd be happy to help..."

Step 8: Execute Business Logic
===============================
If intent requires action:
  - "book_appointment" -> Check calendar availability
  - "take_message" -> Store message, send notification
  - "route_call" -> Initiate transfer to human
  - "faq_query" -> Search knowledge base

Step 9: Text-to-Speech
=======================
Response text sent to Piper TTS:
  - Converts to natural speech
  - Returns audio file
  - FreeSWITCH plays to caller

Step 10: Loop or End
=====================
Conversation loops (Step 5-9) until:
  - Caller hangs up
  - Call transferred
  - Timeout (max call duration)
  - Completion (appointment booked, message taken)

Step 11: Post-Call Processing
==============================
Celery background tasks:
  - Save call record to PostgreSQL
  - Save full transcription
  - Send SMS notification (if urgent)
  - Send email summary
  - Update analytics counters
  - Trigger webhooks

Step 12: Dashboard Update
==========================
WebSocket broadcast:
  - Real-time update to dashboard
  - Call appears in recent activity
  - Analytics charts update
```

### Sequence Diagram

```
Caller    FreeSWITCH    ESL        Telephony    Whisper    Ollama    Piper     DB      Dashboard
  |           |          |            |           |          |         |       |           |
  |--INVITE-->|          |            |           |          |         |       |           |
  |<---200----|          |            |           |          |         |       |           |
  |---RTP---->|          |            |           |          |         |       |           |
  |           |--EVENT-->|            |           |          |         |       |           |
  |           |          |---CALL---->|           |          |         |       |           |
  |           |          |            |--TTS req->|          |         |       |           |
  |           |          |            |<---audio--|          |         |       |           |
  |<---PLAY---|          |            |           |          |         |       |           |
  |"Welcome!" |          |            |           |          |         |       |           |
  |           |          |            |           |          |         |       |           |
  |====SPEECH===========>|            |           |          |         |       |           |
  |           |          |            |<-chunks-->|          |         |       |           |
  |           |          |            |--STT---->|          |         |       |           |
  |           |          |            |<--text---|          |         |       |           |
  |           |          |            |---------LLM req-------------->|         |           |
  |           |          |            |<--------response---------------|         |           |
  |           |          |            |--TTS------------------------------->|     |           |
  |           |          |            |<--audio-------------------------------|     |           |
  |<---PLAY---|          |            |           |          |         |       |           |
  |"I'd be..."|          |            |           |          |         |       |           |
  |           |          |            |           |          |         |       |           |
  |           |          |            |--SAVE---------------------------------------->|     |
  |           |          |            |<--OK------------------------------------------|     |
  |           |          |            |--WS------------------------------------------------>|
  |           |          |            |           |          |         |       |     | UPDATE|
  |           |          |            |           |          |         |       |     |       |
  |--BYE----->|          |            |           |          |         |       |     |       |
  |           |--EVENT-->|            |           |          |         |       |     |       |
  |           |          |--HANGUP--->|           |          |         |       |     |       |
  |           |          |            |--FINAL--------------------------------------->|     |
```

---

## Component Descriptions

### 1. Telephony Engine (Python)

**Responsibility**: All real-time call handling, audio I/O, and state management.

**Key Modules**:
- `esl_client.py` -- Event Socket connection to FreeSWITCH
- `call_session.py` -- Per-call state machine and context
- `audio_pipeline.py` -- Audio capture, buffering, playback
- `vad.py` -- Voice activity detection
- `conversation_manager.py` -- Dialogue history and context

**Technology**: Python 3.11, asyncio, aiohttp

**Why asyncio**: Handles hundreds of concurrent WebSocket/audio connections with minimal resource usage. Single-threaded event loop avoids GIL contention.

### 2. AI Pipeline Service

**Responsibility**: End-to-end AI processing (STT, LLM, TTS).

**Sub-components**:
- **Whisper STT**: OpenAI's Whisper model via faster-whisper. Supports large-v3, medium, small models. Quantized to int8 for CPU inference.
- **Ollama LLM**: Meta's Llama 3.2 served via Ollama. Supports 3B (fast) and 7B (better quality) variants. GGUF quantized for efficient inference.
- **Piper TTS**: Fast neural TTS. ONNX Runtime for CPU/GPU acceleration. Multiple voice options.

**Optimization Strategy**:
- Model quantization (4-bit for LLM, int8 for STT)
- Audio chunk streaming (no full-file buffering)
- Response caching for common queries
- Warm model keeping (models stay loaded)

### 3. Orchestration Layer (FastAPI)

**Responsibility**: REST API, WebSocket management, background tasks, authentication.

**Key Modules**:
- `api/` -- 95+ REST endpoints organized by domain
- `ws/` -- WebSocket handlers for real-time features
- `tasks/` -- Celery background task definitions
- `auth/` -- JWT authentication and authorization
- `models/` -- SQLAlchemy ORM models

**Technology**: FastAPI 0.115, Pydantic v2, SQLAlchemy 2.0, Celery 5.4

### 4. Business Logic Service

**Responsibility**: Domain-specific business rules.

**Modules**:
- `messages/` -- Message taking, storage, retrieval
- `appointments/` -- Availability checking, booking, reminders
- `call_routing/` -- Rule-based routing engine
- `knowledge_base/` -- Document processing, chunking, retrieval
- `notifications/` -- SMS, email, webhook delivery

### 5. Integration Hub

**Responsibility**: External service integrations.

**Integrations**:
- **Google Calendar**: OAuth2, two-way sync via Google Calendar API v3
- **SMTP**: Generic email via any SMTP server
- **Twilio**: SMS notifications via Twilio API
- **Webhooks**: Outbound HTTP callbacks for events
- **Zapier/Make.com**: Compatible webhook endpoints

### 6. Database Layer (PostgreSQL)

**Responsibility**: Persistent data storage with full ACID compliance.

**Schema highlights**:
- 30+ tables across tenants, calls, messages, appointments, analytics
- Row-level security for tenant isolation
- JSONB columns for flexible metadata
- Partitioned tables for call logs (by month)
- Full-text search indexes on transcriptions

### 7. Client Dashboard (React 19)

**Responsibility**: Administrative web interface.

**Features**:
- Real-time call monitoring via WebSocket
- Interactive charts and analytics
- Tenant configuration forms
- Knowledge base document management
- User and permission management

**Technology**: React 19, TypeScript 5.6, Tailwind CSS 3.4, Vite 6

---

## Technology Choices

### Why FreeSWITCH?

| Alternative | Why Not Selected | Why FreeSWITCH Wins |
|-------------|-----------------|---------------------|
| Asterisk | Complex configuration, weaker WebRTC | Better ESL API, more flexible media handling |
| Kamailio | Just a SIP proxy, no media | Full PBX with media, conferencing, IVR |
| Janus | WebRTC-focused, no PSTN | Native SIP, PSTN gateway support |
| Custom | Massive development effort | Battle-tested, 15+ years production use |

### Why Local AI (Ollama + Whisper + Piper)?

| Alternative | Monthly Cost | Privacy | Latency | Quality |
|-------------|-------------|---------|---------|---------|
| OpenAI GPT-4o | $200-500 | Cloud | 1-2s | Excellent |
| Twilio + GPT | $300-600 | Cloud | 2-4s | Excellent |
| Google Dialogflow | $100-400 | Cloud | 1-3s | Good |
| **Local (Owlbell)** | **$0** | **Local** | **2-5s** | **Good** |

Trade-off: Slightly higher latency vs. infinite privacy and zero cost. GPU improves latency to match cloud solutions.

### Why FastAPI over Django/Flask?

- **Native async**: Handles WebSocket and concurrent requests efficiently
- **Auto-generated docs**: OpenAPI/Swagger UI out of the box
- **Type safety**: Pydantic integration catches errors early
- **Performance**: One of the fastest Python frameworks
- **Modern**: Built on Starlette + Pydantic, designed for APIs

### Why SQLAlchemy 2.0 with asyncpg?

- **Async support**: Non-blocking database operations
- **Type hints**: Full mypy compatibility
- **Migrations**: Alembic integration for schema evolution
- **Flexibility**: Can switch to MySQL or SQLite if needed

### Why React 19?

- **Server Components**: Reduced client-side JavaScript
- **Concurrent features**: Better perceived performance
- **Ecosystem**: Largest UI component ecosystem
- **TypeScript**: First-class type safety

### Why Docker Compose over Kubernetes?

For a single-server deployment:
- **Simplicity**: One `docker compose up` vs. cluster setup
- **Resources**: K8s control plane needs 2GB+ RAM
- **Learning curve**: Compose is accessible to non-DevOps users
- **Migration path**: Kompose can convert to K8s later

Future: Kubernetes Helm charts will be provided for multi-server deployments.

---

## Multi-Tenancy Design

### Architecture: Shared Database, Schema Isolation

```
PostgreSQL Database: answerflow
|
|-- Schema: tenant_abc123  (Smith Dental)
|   |-- Table: calls
|   |-- Table: messages
|   |-- Table: appointments
|   |-- Table: knowledge_chunks
|
|-- Schema: tenant_def456  (Johnson Law)
|   |-- Table: calls
|   |-- Table: messages
|   |-- Table: appointments
|   |-- Table: knowledge_chunks
|
|-- Schema: shared
    |-- Table: tenants
    |-- Table: users
    |-- Table: api_keys
```

### Tenant Identification

```python
# Tenant resolution middleware
async def tenant_middleware(request: Request, call_next):
    # Priority 1: Subdomain (smith-dental.answerflow.com)
    host = request.headers.get("host", "")
    subdomain = host.split(".")[0]
    tenant = await get_tenant_by_slug(subdomain)
    
    # Priority 2: X-Tenant-ID header
    if not tenant:
        tenant_id = request.headers.get("X-Tenant-ID")
        tenant = await get_tenant_by_id(tenant_id)
    
    # Priority 3: JWT token claim
    if not tenant:
        token = extract_jwt(request)
        tenant_id = token.get("tenant_id")
        tenant = await get_tenant_by_id(tenant_id)
    
    # Attach to request context
    request.state.tenant = tenant
    response = await call_next(request)
    return response
```

### Data Isolation Guarantees

1. **Database**: Row-level security policies enforce tenant filtering
2. **API**: All queries include `tenant_id` filter automatically
3. **Cache**: Redis keys prefixed with `tenant:{id}:`
4. **AI**: Per-tenant knowledge base context injection
5. **Files**: Per-tenant upload directories
6. **Logs**: Log entries tagged with tenant identifier

### Resource Limits (Per Tenant)

| Resource | Free Tier | Pro Tier | Enterprise |
|----------|-----------|----------|------------|
| Concurrent calls | 2 | 10 | Unlimited |
| Knowledge base size | 10MB | 100MB | 1GB |
| Users | 2 | 10 | Unlimited |
| API calls/day | 1,000 | 10,000 | Unlimited |
| Call history retention | 30 days | 1 year | Unlimited |

---

## Security Architecture

See [SECURITY.md](SECURITY.md) for complete details. Key points:

### Authentication

```
Client --> POST /auth/login {email, password}
             |
             v
         +---+---+
         |  API  |
         +---+---+
             |
             v
         Verify bcrypt hash
             |
             v
         Generate JWT (access + refresh)
             |
             v
         Return {access_token, refresh_token}

Subsequent requests:
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Authorization (RBAC)

```
Roles:
  - super_admin: Full system access
  - tenant_admin: Full tenant access
  - manager: View + configure, no billing
  - agent: View calls/messages, take notes
  - readonly: View only

Permissions are checked at:
  - API endpoint decorator level (@require_role)
  - Database query level (tenant isolation)
  - WebSocket subscription level (event filtering)
```

### Data Encryption

| Layer | Method | Details |
|-------|--------|---------|
| Transport | TLS 1.3 | All HTTP, WebSocket, SIP traffic |
| Database | AES-256 | Encrypted at rest via PostgreSQL TDE |
| Secrets | Docker Secrets | Stored in Docker swarm secrets or .env |
| Backups | GPG encryption | AES-256 encrypted before upload |

### Network Security

```
Internet
    |
    | (HTTPS :443)
    v
+---+---+
| Nginx |  SSL termination, rate limiting
+---+---+  WAF rules, request filtering
    |
    | (HTTP :8000 internal)
    v
+---+---+
| FastAPI|  JWT validation, tenant isolation
+---+---+  Input validation, SQL injection prevention
    |
    | (internal Docker network)
    v
+---+---+   +---+---+   +---+---+
|PostgreSQL|  | Redis |   |FreeSWITCH|
+---------+  +-----+   +---------+
              (no external exposure)
```

---

## Database Schema Overview

### Core Tables

```
tenants
  id (PK, UUID)
  slug (unique, indexed)
  name
  phone_number
  timezone
  business_hours (JSONB)
  ai_config (JSONB)
  created_at, updated_at

calls
  id (PK, UUID)
  tenant_id (FK)  -- tenant isolation
  phone_number
  caller_id
  direction (inbound/outbound)
  status (ringing/connected/ended)
  duration_seconds
  transcription (text, full-text indexed)
  recording_path
  sentiment_score
  created_at, ended_at

messages
  id (PK, UUID)
  tenant_id (FK)
  call_id (FK)
  caller_name
  caller_phone
  content
  urgency (low/medium/high)
  notified (boolean)
  created_at

appointments
  id (PK, UUID)
  tenant_id (FK)
  call_id (FK)
  google_event_id
  title
  description
  start_time
  end_time
  attendee_name
  attendee_phone
  attendee_email
  status (scheduled/completed/cancelled)
  created_at

knowledge_documents
  id (PK, UUID)
  tenant_id (FK)
  filename
  file_path
  file_size
  mime_type
  chunk_count
  is_active
  created_at

knowledge_chunks
  id (PK, UUID)
  tenant_id (FK)
  document_id (FK)
  content (text)
  embedding (vector, 384-dim)
  chunk_index

users
  id (PK, UUID)
  tenant_id (FK, nullable for super_admins)
  email (unique)
  password_hash
  full_name
  role (super_admin/tenant_admin/manager/agent/readonly)
  is_active
  last_login
  created_at

call_routing_rules
  id (PK, UUID)
  tenant_id (FK)
  name
  priority (integer)
  condition (JSONB)
  action (JSONB)
  is_active

api_keys
  id (PK, UUID)
  tenant_id (FK)
  key_hash
  name
  permissions (JSONB)
  rate_limit
  expires_at
  last_used_at
  created_at
```

### Indexes

```sql
-- Tenant isolation (all tenant-scoped tables)
CREATE INDEX idx_calls_tenant_id ON calls(tenant_id);
CREATE INDEX idx_messages_tenant_id ON messages(tenant_id);
CREATE INDEX idx_appointments_tenant_id ON appointments(tenant_id);

-- Full-text search
CREATE INDEX idx_calls_transcription_search ON calls USING GIN (to_tsvector('english', transcription));
CREATE INDEX idx_messages_content_search ON messages USING GIN (to_tsvector('english', content));

-- Time-range queries (analytics)
CREATE INDEX idx_calls_created_at ON calls(created_at);
CREATE INDEX idx_calls_tenant_created ON calls(tenant_id, created_at);

-- Phone number lookups
CREATE INDEX idx_calls_phone ON calls(phone_number);
CREATE INDEX idx_messages_phone ON messages(caller_phone);
```

---

## API Design

### REST Principles

- **Resource-oriented**: `/calls`, `/messages`, `/appointments`
- **HTTP methods**: GET, POST, PUT, PATCH, DELETE
- **Status codes**: Standard HTTP semantics
- **Pagination**: Cursor-based for large collections
- **Filtering**: Query parameters with type validation
- **Sorting**: `sort=-created_at` (descending)
- **Expansion**: `?expand=tenant,call` for related objects
- **Versioning**: URL path `/api/v1/...`

### WebSocket Protocol

```
Connection: wss://ws.your-domain.com/api/v1/ws/live
Authentication: Bearer token in query param or Sec-WebSocket-Protocol

Subscribe to events:
  {"type": "subscribe", "channels": ["calls", "messages"]}

Receive events:
  {"type": "call.started", "data": {"call_id": "...", ...}}
  {"type": "call.ended", "data": {"call_id": "...", "duration": 120, ...}}
  {"type": "message.received", "data": {"message_id": "...", ...}}

Heartbeat:
  {"type": "ping"} -> {"type": "pong"}
```

Complete API documentation: [API_REFERENCE.md](API_REFERENCE.md)

---

## Scaling Strategy

### Single Server (Current)

```
Capacity: 3-40 concurrent calls (depending on CPU/GPU)
Suitable for: 1-10 tenants, small to medium businesses
```

### Vertical Scaling

```
Upgrade server specs:
  - More RAM: Fit larger LLM (7B, 13B parameters)
  - More CPU cores: Handle more concurrent calls
  - Add GPU: Reduce AI latency by 60-80%
  
Cost increase: $5/month -> $50/month
Capacity: Up to 100 concurrent calls
```

### Horizontal Scaling (Future)

```
                    +-------+
                    | Nginx |
                    | (LB)  |
                    +---+---+-------+
                        |           |
              +---------v+    +-----v-------+
              | API Srv 1|    | API Srv 2   |
              | (Docker) |    | (Docker)    |
              +----+-----+    +------+------+
                   |                  |
              +----v-----------------v-----+
              |    PostgreSQL (primary)      |
              |    Redis (cluster)           |
              |    FreeSWITCH (SBC)          |
              +-------------------------------+

Components:
  - Nginx load balancer with health checks
  - Multiple API servers (stateless)
  - PostgreSQL streaming replication
  - Redis Sentinel for HA
  - Dedicated FreeSWITCH SBC + multiple media servers
  - Shared storage for recordings (NFS/S3)
  
Capacity: 500+ concurrent calls
Cost: $200-500/month
```

### AI-Specific Scaling

```
Option 1: Multiple Ollama instances
  - Each handles subset of requests
  - Models loaded per-instance
  
Option 2: GPU cluster with Ollama
  - Multi-GPU server
  - Ollama distributes across GPUs
  
Option 3: vLLM (for high throughput)
  - Continuous batching
  - PagedAttention for memory efficiency
  - 10x throughput improvement
```

---

## Disaster Recovery

### Backup Strategy

| Data | Frequency | Method | Retention |
|------|-----------|--------|-----------|
| Database | Daily | `pg_dump` | 30 days |
| Call recordings | Weekly | `rsync` to remote | 1 year |
| Knowledge base docs | Daily | `tar` + encrypt | 90 days |
| Configuration | On change | Git + `.env` backup | Forever |
| AI models | Once | Cache download script | N/A |

### Automated Backup Script

```bash
#!/bin/bash
# /opt/answerflow/scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups/answerflow/$DATE
mkdir -p $BACKUP_DIR

# Database
docker exec answerflow-postgres pg_dump -U answerflow answerflow | \
  gzip > $BACKUP_DIR/database.sql.gz

# Call recordings
tar czf $BACKUP_DIR/recordings.tar.gz /opt/answerflow/data/recordings/

# Knowledge base documents
tar czf $BACKUP_DIR/kb.tar.gz /opt/answerflow/data/kb/

# Configuration
cp /opt/answerflow/.env $BACKUP_DIR/env_backup

# Encrypt
gpg --symmetric --cipher-algo AES256 --output $BACKUP_DIR.tar.gz.gpg $BACKUP_DIR

# Upload to remote (configure rclone for S3/B2/etc.)
rclone copy $BACKUP_DIR.tar.gz.gpg remote:answerflow-backups/

# Cleanup old backups
find /backups/answerflow -type d -mtime +30 -exec rm -rf {} \;
```

### Recovery Procedure

```
1. Provision new server (follow Getting Started)
2. Restore .env from backup
3. Start base services: docker compose up -d postgres redis
4. Restore database:
   gunzip < database.sql.gz | docker exec -i answerflow-postgres psql -U answerflow
5. Restore recordings and KB: tar xzf recordings.tar.gz -C /
6. Start all services: docker compose up -d
7. Verify: curl http://localhost/api/v1/health
```

**RTO** (Recovery Time Objective): 30 minutes
**RPO** (Recovery Point Objective): 24 hours (daily backups)

---

## Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) -- Deploy your first instance
- [API_REFERENCE.md](API_REFERENCE.md) -- Complete API documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) -- Production deployment guide
- [SECURITY.md](SECURITY.md) -- Security hardening
- [DEVELOPMENT.md](DEVELOPMENT.md) -- Development environment setup
