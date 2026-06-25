# Owlbell — Demo Walkthrough

**Location:** `docs/DEMO_WALKTHROUGH.md`

This guide walks you through the Owlbell demo from end to end. After
completing the [setup](#prerequisites), you will simulate an inbound phone
call, interact with the AI receptionist, and observe the results in the
dashboard.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Starting the System](#starting-the-system)
3. [Exploring the Demo Tenant](#exploring-the-demo-tenant)
4. [Simulating an Inbound Call](#simulating-an-inbound-call)
5. [What to Say to the AI](#what-to-say-to-the-ai)
6. [Viewing the Call in the Dashboard](#viewing-the-call-in-the-dashboard)
7. [Checking Messages Left](#checking-messages-left)
8. [Viewing Appointments](#viewing-appointments)
9. [Exploring the Knowledge Base](#exploring-the-knowledge-base)
10. [Managing Routing Rules](#managing-routing-rules)
11. [AI Prompt Customization](#ai-prompt-customization)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- [Docker](https://docs.docker.com/get-docker/) 24.0+
- [Docker Compose](https://docs.docker.com/compose/install/) v2+
- 4 GB RAM available
- Ports 5173, 8000, 5432, 6379 free on localhost
- The Owlbell repository cloned locally

Verify prerequisites:

```bash
docker --version          # Docker 24.0+
docker compose version    # Compose v2+
python3 --version         # Python 3.11+
```

---

## Starting the System

### Quick Start (One Command)

```bash
cd /path/to/answerflow
./infrastructure/scripts/first-run.sh
```

This script will:
1. Check prerequisites
2. Create a `.env` file with auto-generated secrets
3. Start PostgreSQL, Redis, and all AI services
4. Run database migrations
5. Seed demo data (Smith Dental Clinic)
6. Start the API server and dashboard
7. Run health checks

**Expected output:**
```
[INFO]  All prerequisites satisfied
[OK]   All required ports are available
[INFO]  Creating .env configuration...
[OK]   .env created
...
[OK]   Demo data seeded successfully
[OK]   All services started
```

### Manual Start (Alternative)

If you prefer manual control:

```bash
# 1. Create environment file
cp infrastructure/docker/.env.template .env
# Edit .env with your settings

# 2. Start infrastructure
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis

# 3. Run migrations
cd backend && alembic upgrade head

# 4. Seed demo data
python -m backend.db.seed --demo

# 5. Start all services
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

### Verify Everything is Running

```bash
# Check service status
docker compose ps

# Expected output:
# NAME                STATUS          PORTS
# answerflow-api      Up 10 seconds   0.0.0.0:8000->8000/tcp
# answerflow-db       Up 15 seconds   0.0.0.0:5432->5432/tcp
# answerflow-redis    Up 15 seconds   0.0.0.0:6379->6379/tcp
# answerflow-fs       Up 10 seconds   0.0.0.0:5060->5060/tcp
# answerflow-whisper  Up 10 seconds   0.0.0.0:8001->8001/tcp
# answerflow-piper    Up 10 seconds   0.0.0.0:8002->8002/tcp

# Health check
curl http://localhost:8000/api/v1/health
# {"status": "healthy", "database": "connected", "redis": "connected"}
```

---

## Exploring the Demo Tenant

### What Was Seeded

The `first-run.sh` script creates a complete demo tenant:

| Entity | Count | Details |
|--------|-------|---------|
| **Tenant** | 1 | Smith Dental Clinic |
| **User** | 1 | Dr. Sarah Smith (admin) |
| **FAQ Entries** | 10 | Common dental questions |
| **Routing Rules** | 5 | Time-based, intent-based, fallback |
| **Business Hours** | 7 | Mon-Fri 9-5, Sat 9-1, Sun closed |
| **Holidays** | 9 | Major US holidays with hours |
| **AI Prompts** | 5 | System, greeting, hold, closing |
| **Sample Calls** | 10 | 3 bookings, 4 messages, 2 FAQ, 1 transfer |
| **Appointments** | 5 | Various types and statuses |
| **Conversation** | 1 | Detailed example with 5 messages |

### Login to the Dashboard

1. Open your browser: **http://localhost:5173**
2. Log in with:
   - **Email:** `dr.smith@smithdental.example.com`
   - **Password:** `DemoPass123!`
3. You should see the main dashboard with:
   - Call activity overview
   - Recent calls list
   - Appointment summary
   - Quick stats cards

### Dashboard Overview (Screenshot Description)

After logging in, the dashboard displays:

**Top Navigation Bar**
- Smith Dental Clinic logo and name
- Navigation links: Dashboard, Calls, Appointments, Knowledge Base, Settings
- User avatar dropdown (Dr. Sarah Smith)
- Notification bell with 3 unread indicators

**Stats Cards Row**
- Today's Calls: "8 calls" with a green trend indicator
- Avg Call Duration: "2m 34s"
- AI Resolution Rate: "90%"
- Voicemails: "1 new"

**Main Content Area**
- Left panel: Recent calls table with caller name, duration, result, and timestamp
- Right panel: Upcoming appointments for today and tomorrow
- Bottom: AI conversation quality chart (7-day trend)

---

## Simulating an Inbound Call

### Method 1: API Endpoint (Recommended)

Use the provided simulation endpoint to trigger a call:

```bash
# Simulate an inbound call
curl -X POST http://localhost:8000/api/v1/calls/simulate \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: smith-dental" \
  -d '{
    "to": "+1-555-0100",
    "from": "+1-555-0999",
    "caller_name": "Alice Johnson",
    "scenario": "appointment_request"
  }'
```

**Expected response:**
```json
{
  "call_id": "abc-123-def",
  "status": "initiated",
  "ai_agent": "connected",
  "ws_url": "ws://localhost:5066/ws/calls/abc-123-def"
}
```

### Method 2: WebSocket Direct Connection

For testing the real-time audio flow:

```bash
# Connect to the call WebSocket
wscat -c "ws://localhost:5066/ws/calls/demo-call-001"

# Send audio (base64-encoded PCM 16kHz)
# Or send text for testing:
{ "type": "text", "content": "Hello, I'd like to schedule a cleaning" }
```

### Method 3: Using the Test Script

```bash
# Run the built-in call simulator
cd backend
python -m tests.e2e.simulate_call \
  --tenant smith-dental \
  --phone "+1-555-0999" \
  --script "new_patient"
```

### Expected Call Flow

```
1. Inbound call to +1-555-0100 (Smith Dental)
   |
2. FreeSWITCH receives call
   |
3. Routing rule matches "Business Hours -> AI"
   |
4. AI Agent answers:
   "Good morning, thank you for calling Smith Dental Clinic.
    My name is Alex, your virtual receptionist.
    How may I assist you today?"
   |
5. STT converts caller speech to text
   |
6. LLM processes intent, generates response
   |
7. TTS converts response to audio
   |
8. Call completes -> summary stored in DB
```

---

## What to Say to the AI

The AI receptionist understands natural language. Here are suggested
test scripts organized by scenario.

### Scenario A: Schedule a Cleaning (Appointment Booking)

**You:** "Hi, I'd like to schedule a teeth cleaning."

**Expected AI Response:**
> "Hello! I'd be happy to help you schedule a cleaning. I have availability
> on Thursday at 9 AM or Friday at 10 AM. Which would work better for you?"

**You:** "Friday at 10 sounds good."

**Expected AI Response:**
> "Perfect! I've scheduled your routine cleaning for Friday at 10:00 AM.
> Please arrive 10 minutes early. We look forward to seeing you!
> Is there anything else I can help you with?"

**You:** "No, that's all. Thank you!"

**Expected AI Response:**
> "Thank you for calling Smith Dental Clinic. Have a wonderful day!"

### Scenario B: Ask About Hours (FAQ)

**You:** "What are your office hours?"

**Expected AI Response:**
> "Our office hours are Monday through Friday from 9:00 AM to 5:00 PM, and
> Saturday from 9:00 AM to 1:00 PM. We are closed on Sundays and major
> holidays."

### Scenario C: Emergency Triage (Transfer)

**You:** "I'm in a lot of pain, I think I have a dental emergency"

**Expected AI Response:**
> "I'm sorry to hear you're in pain. I'll help you right away. Can you tell
> me more about your symptoms? Are you experiencing severe pain, bleeding,
> or swelling?"

**You:** "Yes, severe pain from a knocked-out tooth"

**Expected AI Response:**
> "That sounds like a dental emergency. I'm going to transfer you to our
> emergency line right away. Please hold while I connect you."

### Scenario D: Leave a Message

**You:** "Can I leave a message for Dr. Smith?"

**Expected AI Response:**
> "Of course! Dr. Smith is currently with a patient, but I'd be happy to
> take a detailed message. May I have your name and callback number?"

**You:** "This is Bob Wilson, my number is 555-0303"

**Expected AI Response:**
> "Thank you, Bob. And what message would you like me to pass along to
> Dr. Smith?"

### Scenario E: Ask About Insurance

**You:** "Do you take Delta Dental insurance?"

**Expected AI Response:**
> "Yes, we accept most major dental insurance plans including Delta Dental.
> Please bring your insurance card to your appointment and we will verify
> your benefits before treatment."

### Testing All FAQ Variants

Try these alternate phrasings to test the AI's semantic matching:

| Intent | Try Saying... |
|--------|---------------|
| Hours | "When are you open?", "How late are you open?", "Weekend hours?" |
| Insurance | "What insurance do you accept?", "Are you in-network?" |
| Scheduling | "Can I book a cleaning?", "Make an appointment" |
| Emergency | "Toothache", "Bleeding gums", "Knocked out tooth" |
| Whitening | "Teeth bleaching", "Do you whiten teeth?" |
| Children | "Pediatric dentist?", "Do you see kids?" |
| Payment | "Credit cards?", "CareCredit?", "Payment plans?" |
| Location | "Address?", "Where are you?", "Parking?" |

---

## Viewing the Call in the Dashboard

### Step 1: Navigate to the Calls Page

After making a test call, click **"Calls"** in the top navigation.

### Step 2: Calls List (Screenshot Description)

The Calls page displays a table with columns:

| Column | Example Value |
|--------|--------------|
| Time | "10:23 AM" |
| Caller | "Alice Johnson (+1-555-0999)" |
| Duration | "3m 12s" |
| Type | "Inbound" |
| Result | "Appointment Booked" |
| AI Handled | Yes (green checkmark) |
| Sentiment | Positive (smiley icon) |
| Actions | View details, Play recording |

### Step 3: Call Detail View

Click on any call row to open the detail panel:

**Left Panel — Call Summary**
- Caller information (name, number, location estimate)
- Call timeline: ring -> answer -> hold -> end
- AI model used (llama3.1:8b)
- Token usage: 312 tokens
- Estimated cost: $0.024
- Sentiment score: 0.72 (positive)
- Intent detected: "appointment"

**Right Panel — Transcript**
```
AI:  "Good morning, thank you for calling Smith Dental Clinic..."
You: "Hi, I'd like to schedule a teeth cleaning."
AI:  "Hello! I'd be happy to help you schedule a cleaning..."
You: "Friday at 10 sounds good."
AI:  "Perfect! I've scheduled your routine cleaning for Friday..."
```

**Bottom Panel — Action Buttons**
- Play audio recording
- Download transcript as PDF
- Add note
- Follow up (send email/SMS)

### Step 4: Expected Results

For each call type, the dashboard shows different information:

**Appointment Booking Call**
- Result badge: "Appointment Booked" (green)
- Linked appointment card appears in the right panel
- Transcript highlights: `[ACTION: book_appointment]`

**FAQ Answered Call**
- Result badge: "FAQ Answered" (blue)
- FAQ source shown: "Matched: office_hours"
- Duration typically shorter (1-2 minutes)

**Transferred Call**
- Result badge: "Transferred" (orange)
- Transfer target: "+1-555-0199 (Emergency Line)"
- Hold duration shown in timeline

**Voicemail Call**
- Result badge: "Voicemail" (purple)
- Voicemail player with waveform visualization
- AI transcription of voicemail message

---

## Checking Messages Left

### Via Dashboard

1. Click **"Calls"** in the navigation
2. Filter by **Result: Message Taken** using the dropdown
3. You should see 4 message calls from the seed data

**Example — Patricia Moore message:**
- Caller: Patricia Moore (+1-555-0204)
- Duration: 2m 19s
- Result: Message Taken
- Transcript excerpt:
  > "...I'd like to speak with Dr. Smith about a billing question..."

### Via API

```bash
# List all calls with messages
curl "http://localhost:8000/api/v1/calls?result=success&intent=message" \
  -H "X-Tenant-ID: smith-dental" \
  -H "Authorization: Bearer <your-jwt-token>"

# Get specific call details
curl "http://localhost:8000/api/v1/calls/66666666-6666-6666-6666-000000000004" \
  -H "Authorization: Bearer <your-jwt-token>"
```

### Message Details

Each message entry includes:
- Caller name and number
- Time of call
- Full transcript
- AI-generated summary
- Suggested follow-up action
- Option to mark as "followed up"

---

## Viewing Appointments

### Dashboard Calendar View

1. Click **"Appointments"** in the navigation
2. The calendar view shows all scheduled appointments

**June 2024 Calendar (Screenshot Description):**

```
    Mon    Tue    Wed    Thu    Fri    Sat    Sun
                          13     14*    15     16
     17*    18*    19*    20     21     22     23
```

`*` indicates scheduled appointments:
- **June 14 (Fri) 10:00 AM** — John Williams — Routine Cleaning (confirmed)
- **June 17 (Mon) 9:00 AM** — Karen Martinez — New Patient Exam (pending)
- **June 18 (Tue) 2:00 PM** — Maria Garcia — Whitening Consultation (confirmed)
- **June 19 (Wed) 3:00 PM** — Thomas Wright — Cavity Filling (confirmed)
- **June 13 (Thu) 11:00 AM** — Robert Chen — Rescheduled Check-Up (confirmed)

### Appointment Detail Card

Click any appointment to view details:

```
┌─────────────────────────────────────────────┐
│  Routine Cleaning                           │
│  John Williams                              │
│  📞 +1-555-0201                             │
│                                             │
│  📅 Friday, June 14, 2024                   │
│  🕐 10:00 AM — 10:45 AM                     │
│  📍 Smith Dental Clinic, Suite 200          │
│                                             │
│  Status: ✅ CONFIRMED (by AI)               │
│  Source: Call booking                       │
│  Sync: Pending → Google Calendar            │
│                                             │
│  [Edit] [Cancel] [Send Reminder] [Check In] │
└─────────────────────────────────────────────┘
```

### Via API

```bash
# List upcoming appointments
curl "http://localhost:8000/api/v1/appointments?status=confirmed,pending" \
  -H "Authorization: Bearer <your-jwt-token>"

# Get specific appointment
curl "http://localhost:8000/api/v1/appointments/77777777-7777-7777-7777-000000000001" \
  -H "Authorization: Bearer <your-jwt-token>"
```

---

## Exploring the Knowledge Base

### FAQ Management

1. Click **"Knowledge Base"** in the navigation
2. View all 10 pre-loaded FAQ entries

**FAQ List View:**

| Question | Category | Uses | Status |
|----------|----------|------|--------|
| What are your office hours? | hours | 12 | Active |
| Do you take insurance? | insurance | 8 | Active |
| How do I schedule an appointment? | scheduling | 15 | Active |
| What should I do in a dental emergency? | emergency | 3 | Active |
| Do you offer teeth whitening? | services | 6 | Active |

### Adding a New FAQ

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/faq \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "question": "Do you offer Invisalign?",
    "answer": "Yes! Dr. Smith is a certified Invisalign provider...",
    "category": "orthodontics",
    "tags": ["invisalign", "orthodontics", "alignment"],
    "question_variants": [
      "Can I get Invisalign here?",
      "Do you do clear aligners?"
    ]
  }'
```

### Testing FAQ Matching

Use the FAQ test endpoint to see how questions are matched:

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/faq/test-match \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{"query": "What time do you close?"}'

# Expected response:
# {
#   "matched_faq_id": "aaaaaaaa-aaaa-aaaa-aaaa-000000000001",
#   "question": "What are your office hours?",
#   "confidence": 0.92,
#   "answer": "Our office hours are Monday through Friday..."
# }
```

---

## Managing Routing Rules

### View Current Rules

1. Click **"Settings"** then **"Routing Rules"**

**Rules Table:**

| Priority | Name | Type | Action | Status |
|----------|------|------|--------|--------|
| 5 | Emergency Keyword -> Transfer | intent_based | transfer | Active |
| 10 | After-Hours -> AI Agent | time_based | answer | Active |
| 20 | New Patient -> Book Consultation | intent_based | answer | Active |
| 30 | Business Hours -> AI Receptionist | time_based | answer | Active |
| 999 | Default Fallback | default | answer | Active |

### How Rules Are Evaluated

Rules are processed in priority order (lowest number first). The first
matching rule determines the action:

```
Incoming Call
    |
    v
+---+----------------------------+
| Priority 5: Emergency?         |
|   Keywords: pain, bleeding...  |
|   -> YES: Transfer to emergency|
|   -> NO: Continue              |
+---+----------------------------+
    |
    v
+---+----------------------------+
| Priority 10: After Hours?      |
|   -> YES: AI Agent + Voicemail |
|   -> NO: Continue              |
+---+----------------------------+
    |
    v
+---+----------------------------+
| Priority 20: New Patient?      |
|   -> YES: Welcome + Consult    |
|   -> NO: Continue              |
+---+----------------------------+
    |
    v
+---+----------------------------+
| Priority 999: Default          |
|   -> Always: AI Receptionist   |
+-------------------------------+
```

### Editing a Rule

Click on any rule to edit:
- Change priority (lower = higher priority)
- Modify keywords or conditions
- Change the action (answer, transfer, voicemail, reject)
- Enable/disable the rule
- Set effective dates (for seasonal rules)

---

## AI Prompt Customization

### Current Prompts

Navigate to **Settings > AI Configuration > Prompts** to view:

**System Prompt (Active)**
```
You are Alex, a warm and professional virtual receptionist at Smith Dental
Clinic. Your personality is friendly, patient, and reassuring...
```

**Greeting Prompt (Active)**
```
Good {time_of_day}, thank you for calling Smith Dental Clinic. My name is
Alex, your virtual receptionist. How may I assist you today?
```

**Hold Message**
```
Thank you for holding. I am connecting you now. If the line is busy, I can
take a detailed message...
```

**Goodbye Message**
```
Thank you for calling Smith Dental Clinic. We appreciate your trust in us.
Have a wonderful day!
```

### Customizing the AI Voice

```bash
# Change voice characteristics
curl -X PATCH http://localhost:8000/api/v1/settings/ai \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "voice_type": "piper_female_1",
    "voice_speed": 0.95,
    "ai_temperature": 0.65,
    "greeting_message": "Welcome to Smith Dental, how can I help?"
  }'
```

### A/B Testing Prompts

Create multiple versions of a prompt and compare performance:

```bash
# Create variant B of the greeting
curl -X POST http://localhost:8000/api/v1/prompts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "name": "Greeting — Casual Variant",
    "prompt_type": "greeting",
    "content": "Hey there! Thanks for calling Smith Dental. What can I do for you?",
    "version": 2,
    "is_active": false
  }'
```

Compare metrics in **Settings > AI Analytics**:
- Avg call duration per prompt
- Satisfaction scores
- FAQ match rates
- Appointment booking rates

---

## Troubleshooting

### Common Issues

#### Dashboard Shows "Connection Error"

```bash
# Check if API is running
curl http://localhost:8000/api/v1/health

# If not, restart:
docker compose -f infrastructure/docker/docker-compose.yml restart api

# Check API logs:
docker compose -f infrastructure/docker/docker-compose.yml logs -f api
```

#### No Audio During Call Simulation

```bash
# Check FreeSWITCH status
docker compose exec freeswitch fs_cli -x "status"

# Check if Piper TTS is running
curl http://localhost:8002/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test"}' \
  --output /tmp/test.wav && file /tmp/test.wav

# Check if Whisper STT is running
curl -X POST http://localhost:8001/v1/audio/transcriptions \
  -F "file=@/tmp/test.wav" \
  -F "model=whisper-1"
```

#### Demo Data Missing

```bash
# Re-seed demo data
cd backend && python -m backend.db.seed --demo

# If database tables are missing:
python -m backend.db.seed --demo --create-tables

# Full reset and re-seed:
python -m backend.db.seed --reset --force
python -m backend.db.seed --demo
```

#### Slow AI Responses

1. Check Ollama model status:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. If using a large model, switch to the lighter one:
   ```bash
   # In .env, set:
   OLLAMA_MODEL=phi3:mini
   ```

3. Restart AI services:
   ```bash
   docker compose restart ollama api
   ```

#### Port Already in Use

```bash
# Find what's using port 8000
lsof -ti:8000

# Kill it or change the port in docker-compose.override.yml:
# ports:
#   - "8080:8000"  # Use 8080 instead
```

### Getting Help

- **API Documentation:** http://localhost:8000/api/v1/docs
- **Logs:** `docker compose logs -f [service]`
- **Database:** Connect with `psql postgresql://answerflow:...`
- **Redis:** `docker compose exec redis redis-cli`

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│              ANSWERFLOW AI — QUICK REFERENCE            │
├─────────────────────────────────────────────────────────┤
│  Dashboard:     http://localhost:5173                   │
│  API Docs:      http://localhost:8000/api/v1/docs       │
│  Health:        http://localhost:8000/api/v1/health     │
├─────────────────────────────────────────────────────────┤
│  Login:         dr.smith@smithdental.example.com        │
│  Password:      DemoPass123!                            │
├─────────────────────────────────────────────────────────┤
│  Demo Phone:    +1-555-0100                             │
│  Emergency:     +1-555-0199                             │
├─────────────────────────────────────────────────────────┤
│  Useful Commands:                                       │
│  docker compose ps               # List services        │
│  docker compose logs -f api      # Tail API logs        │
│  python -m backend.db.seed --demo  # Re-seed data       │
│  make test                       # Run tests            │
├─────────────────────────────────────────────────────────┤
│  Call Scenarios to Try:                                 │
│  1. "Schedule a cleaning"        → Appointment          │
│  2. "What are your hours?"       → FAQ answer           │
│  3. "I have severe tooth pain"   → Emergency transfer   │
│  4. "Message for Dr. Smith"      → Message taken        │
│  5. "Do you take insurance?"     → FAQ answer           │
└─────────────────────────────────────────────────────────┘
```

---

*This walkthrough covers the complete Owlbell demo experience.
For production deployment, see `docs/DEPLOYMENT.md`.*

*Last updated: 2024-06-15*
