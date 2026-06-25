# Owlbell — Live Calling Setup Guide

## What's built

The full telephony stack is now implemented:

- **ESL Client** (`backend/telephony/core/esl_connection.py`) — async FreeSWITCH Event Socket client with auto-reconnect, event subscription, and call control commands (answer, hangup, playback, bridge, record, transfer)
- **Call Handler** (`backend/telephony/core/call_handler.py`) — bridges inbound SIP calls to the AI pipeline: answers calls, plays greeting via Piper TTS, streams audio to the orchestrator WebSocket, handles DTMF (0=operator, 9=repeat), manages call lifecycle
- **Telephony Manager** (`backend/telephony/manager.py`) — lifecycle manager wired into `main.py` startup/shutdown
- **FreeSWITCH Config** (`infrastructure/freeswitch/conf/`) — dialplan, SIP profile (Telnyx/Twilio gateway), ESL config, mod_audio_stream config, module list
- **Orchestrator** (already existed) — WebSocket gateway, session manager, event bus, worker pool, call queue, circuit breakers
- **AI Pipeline** (already existed) — Whisper STT, Ollama LLM, Piper TTS, conversation engine

## What you need to get live calls

### 1. Get a VPS

Minimum specs: 4 vCPU, 8GB RAM, 50GB disk (for local AI models).

Recommended:
- **Oracle Cloud Always Free** — ARM Ampere A1, 4 OCPU / 24GB RAM (free forever)
- **Hetzner** — CAX21 (4 vCPU / 8GB RAM), €7.59/mo

### 2. Get a SIP trunk + phone number

**Telnyx** (recommended — free trial credit):
1. Sign up at https://telnyx.com
2. Buy a number ($1/mo)
3. Create a SIP Trunk → get SIP username + password
4. Set the trunk's "Inbound Voice URL" to your VPS IP
5. Add to `.env`:
   ```
   TELNYX_SIP_USERNAME=your_username
   TELNYX_SIP_PASSWORD=your_password
   ```

**Twilio** (alternative):
1. Sign up at https://twilio.com
2. Buy a number ($1/mo)
3. Create a SIP Trunk
4. Set the trunk's termination/origination URI to your VPS

### 3. Deploy the stack

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone the repo
git clone https://github.com/yourusername/owlbell.git
cd owlbell/project

# Copy env template
cp .env.example .env

# Edit .env — fill in ALL secrets:
nano .env
# Required:
#   POSTGRES_PASSWORD, APP_SECRET_KEY, JWT_SECRET_KEY
#   FREESWITCH_ESL_PASSWORD, MINIO_SECRET_KEY
#   TELNYX_SIP_USERNAME, TELNYX_SIP_PASSWORD
#   OLLAMA_MODEL=phi3:mini (or llama3.1:8b for better quality)
#   WHISPER_MODEL=ggml-base.en.bin
#   OPERATOR_TRANSFER_NUMBER=your-cell-number

# Start the full stack
docker compose -f infrastructure/docker/docker-compose.yml up -d

# Wait for services to be healthy (2-5 min for first boot)
docker compose -f infrastructure/docker/docker-compose.yml ps

# Pull AI models (first time only)
docker exec af_ollama ollama pull phi3:mini
docker exec af_whisper wget -O /models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

### 4. Test the call

```bash
# Check FreeSWITCH is registered to the SIP trunk
docker exec af_freeswitch fs_cli -x "sofia status gateway telnyx"

# You should see "State REGED" — if not, check credentials

# Check the API is running
curl http://localhost:8000/health

# Check the orchestrator is ready
curl http://localhost:8000/api/v1/orchestrator/health

# Make a test call — call your Telnyx number from your phone
# You should hear the AI greeting and be able to have a conversation
```

### 5. Verify the AI pipeline

```bash
# Whisper STT health
docker exec af_whisper curl -s http://localhost:8080/health

# Ollama LLM health
docker exec af_ollama curl -s http://localhost:11434/api/tags

# Piper TTS health
docker exec af_piper curl -s http://localhost:5000/health

# Check orchestrator sessions (should show active call during a call)
curl http://localhost:8000/api/v1/orchestrator/sessions
```

## Architecture (call flow)

```
Caller's Phone
     │ (PSTN)
     ▼
Telnyx SIP Trunk
     │ (SIP/RTP)
     ▼
FreeSWITCH (Docker container)
     │ (ESL — TCP 8021)
     ├─→ CallHandler: answers call, plays greeting
     │
     │ (mod_audio_stream — WebSocket)
     ▼
Orchestrator Gateway (FastAPI WebSocket)
     │
     ├─→ Whisper STT: transcribes caller audio
     ├─→ Ollama LLM: generates AI response
     ├─→ Piper TTS: synthesizes response audio
     │
     │ (WebSocket audio back)
     ▼
FreeSWITCH → RTP → Caller hears AI response
```

## Local development (without Docker)

```bash
# 1. Install FreeSWITCH locally
# macOS: brew install freeswitch
# Ubuntu: apt install freeswitch

# 2. Copy the config
cp -r infrastructure/freeswitch/conf/* /etc/freeswitch/

# 3. Start FreeSWITCH
freeswitch -nonat -np

# 4. Start the backend
cd project/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # fill in values
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. Start Ollama (separate terminal)
ollama serve
ollama pull phi3:mini

# 6. Test with a SIP softphone
# Install Zoiper or Linphone, configure with your SIP credentials
# Call your Telnyx number
```

## Troubleshooting

### FreeSWITCH not registering to SIP trunk
```bash
docker exec af_freeswitch fs_cli -x "sofia status gateway telnyx"
# If state is NOREG or FAILED, check:
# - TELNYX_SIP_USERNAME / TELNYX_SIP_PASSWORD in .env
# - Firewall: UDP 5060 + RTP ports 16384-16484 must be open
```

### AI sounds robotic / slow
- Switch Ollama model: `OLLAMA_MODEL=llama3.1:8b` (better quality, needs more RAM)
- Check GPU: Ollama should use GPU if available (`docker exec af_ollama nvidia-smi`)
- Whisper: use `ggml-small.en.bin` for better accuracy

### No audio / one-way audio
- Check RTP ports are open in firewall (UDP 16384-16484)
- Check `external_rtp_ip` and `external_sip_ip` in vars.xml match your VPS public IP
- If behind NAT, set these to your public IP directly

### Call connects but AI doesn't respond
```bash
# Check orchestrator WebSocket is accessible
docker exec af_freeswitch fs_cli -x "sofia status"
# Check API logs
docker logs af_api --tail 50
# Check if mod_audio_stream is loaded
docker exec af_freeswitch fs_cli -x "module_exists mod_audio_stream"
```

## Cost breakdown

| Item | Cost |
|------|------|
| VPS (Oracle Cloud free tier) | $0 |
| VPS (Hetzner CAX21) | ~$8/mo |
| Telnyx phone number | $1/mo |
| Telnyx inbound minutes | $0.003/min |
| AI models (self-hosted) | $0 |
| **Total (Oracle free tier)** | **$1/mo** |
| **Total (Hetzner)** | **~$9/mo** |
