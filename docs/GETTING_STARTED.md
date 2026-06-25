# Getting Started with Owlbell

**Estimated time: 30 minutes for first call**

This guide walks you through deploying Owlbell from zero to your first AI-answered phone call.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Choose Your Hosting](#step-1-choose-your-hosting)
- [Step 2: Provision Your Server](#step-2-provision-your-server)
- [Step 3: Install Docker](#step-3-install-docker)
- [Step 4: Configure DNS](#step-4-configure-dns)
- [Step 5: Clone and Configure](#step-5-clone-and-configure)
- [Step 6: Start Owlbell](#step-6-start-answerflow-ai)
- [Step 7: Download AI Models](#step-7-download-ai-models)
- [Step 8: Access the Dashboard](#step-8-access-the-dashboard)
- [Step 9: Configure Your First Tenant](#step-9-configure-your-first-tenant)
- [Step 10: Upload FAQ/Knowledge Base](#step-10-upload-faqknowledge-base)
- [Step 11: Connect Google Calendar](#step-11-connect-google-calendar)
- [Step 12: Make Your First Call](#step-12-make-your-first-call)
- [Step 13: Configure SIP Trunk (Optional)](#step-13-configure-sip-trunk-optional)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## Prerequisites

### Required Knowledge

- Basic Linux command line (SSH, editing files)
- Docker and Docker Compose fundamentals
- DNS basics (A records, subdomains)
- Optional: SIP/VoIP concepts for PSTN connectivity

### Required Software

| Software | Minimum Version | Check Command |
|----------|----------------|---------------|
| Docker | 25.0.0 | `docker --version` |
| Docker Compose | 2.27.0 | `docker compose version` |
| Git | 2.40.0 | `git --version` |
| OpenSSL | 3.0 | `openssl version` |

### Hardware Requirements

| Profile | CPU | RAM | Disk | Network | Cost |
|---------|-----|-----|------|---------|------|
| **Minimum** | 4 cores | 8GB | 50GB SSD | 100 Mbps | ~$5/month |
| **Recommended** | 6 cores | 16GB | 100GB SSD | 500 Mbps | ~$10/month |
| **Production** | 8+ cores | 32GB | 200GB SSD | 1 Gbps | ~$20/month |
| **GPU** | 4 cores + GPU | 16GB | 100GB SSD | 500 Mbps | ~$50/month |

> **Note on GPU**: An NVIDIA GPU dramatically improves AI response time (2s vs 5s). Models like GTX 1660, RTX 3060, or newer work well. AMD GPUs are supported via ROCm.

---

## Step 1: Choose Your Hosting

### Option A: Oracle Cloud Always Free (Recommended -- $0/month)

Oracle Cloud offers a generous free tier that can run Owlbell:

- **VM.Standard.E2.1.Micro**: 1 OCPU (AMD), 1GB RAM
- **VM.Standard.A1.Flex**: 4 OCPU (ARM), 24GB RAM
- 200GB block storage
- 10TB monthly data transfer

**Limitations**: 1GB RAM instance needs swap file; ARM instance may have Docker image compatibility issues with some AI models.

### Option B: Hetzner Cloud (~EUR 5.35/month)

Hetzner offers excellent price/performance:

- **CX22**: 2 vCPU (Intel), 4GB RAM, 40GB SSD
- **CPX21**: 4 vCPU (AMD), 8GB RAM, 80GB SSD -- **Recommended**
- **CPX31**: 4 vCPU (AMD), 16GB RAM, 160GB SSD -- **Best value**

### Option C: Self-Hosted / On-Premise

Run on any hardware in your office:

- Old desktop with 8GB+ RAM
- Intel NUC or similar mini PC
- Proxmox/VMware virtual machine

**Advantages**: Complete privacy, no bandwidth limits, low latency
**Requirements**: Static IP address or dynamic DNS, port forwarding on router

### Option D: Other Cloud Providers

| Provider | Instance | Monthly Cost | Notes |
|----------|----------|--------------|-------|
| DigitalOcean | Basic 8GB | $24 | Simple, good docs |
| Linode | Linode 8GB | $24 | Reliable, good support |
| Vultr | Cloud 8GB | $24 | Fast SSDs |
| AWS Lightsail | 4GB | $20 | Free tier available |
| Google Cloud | e2-medium | ~$25 | Sustained use discounts |

---

## Step 2: Provision Your Server

### Oracle Cloud Setup

#### 2.1 Create Account and Instance

1. Go to [cloud.oracle.com](https://cloud.oracle.com) and sign up for a free account
2. Verify your email and phone number (requires credit card for verification, not charged)
3. Once in the console, navigate to **Compute** → **Instances**
4. Click **Create Instance**

#### 2.2 Configure Instance

```
Name: answerflow-ai
Shape: VM.Standard.A1.Flex (ARM)
OCPU: 4
Memory: 24GB
Boot Volume: Ubuntu 24.04, 100GB
Networking: Create new VCN
Add SSH Keys: Generate new or upload your public key
```

#### 2.3 Configure Networking

1. Go to **Networking** → **Virtual Cloud Networks** → Your VCN
2. Click **Security Lists** → **Default Security List**
3. Add these **Ingress Rules**:

| Stateless | Source Type | Source CIDR | IP Protocol | Destination Port | Description |
|-----------|-------------|-------------|-------------|------------------|-------------|
| No | CIDR | 0.0.0.0/0 | TCP | 22 | SSH |
| No | CIDR | 0.0.0.0/0 | TCP | 80 | HTTP |
| No | CIDR | 0.0.0.0/0 | TCP | 443 | HTTPS |
| No | CIDR | 0.0.0.0/0 | TCP | 5060 | SIP |
| No | CIDR | 0.0.0.0/0 | UDP | 5060 | SIP |
| No | CIDR | 0.0.0.0/0 | UDP | 10000-20000 | RTP Media |
| No | CIDR | 0.0.0.0/0 | TCP | 8021 | ESL |

4. Click **Save Security List Rules**

#### 2.4 Get Instance Details

```bash
# Note the public IP from the instance details page
# Download the private key if you generated one
# Set correct permissions on the key
chmod 600 ~/.ssh/answerflow-key.pem
```

#### 2.5 Connect to Instance

```bash
ssh -i ~/.ssh/answerflow-key.pem ubuntu@YOUR_INSTANCE_IP
```

#### 2.6 Add Swap Space (For 1GB RAM Instances Only)

```bash
# Skip this for 8GB+ instances
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Step 3: Install Docker

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release git

# Add Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group (logout/login required after)
sudo usermod -aG docker $USER

# Verify
sudo docker --version
sudo docker compose version

# Re-login to apply docker group
exit
# SSH back in
```

---

## Step 4: Configure DNS

### 4.1 Register a Domain (If You Don't Have One)

Free options:
- **Freenom**: Free .tk, .ml, .ga domains (1 year)
- **DuckDNS**: Free dynamic DNS (duckdns.org subdomain)
- **No-IP**: Free dynamic DNS

Recommended budget options:
- **Cloudflare Registrar**: Cost-price domains (~$9/year for .com)
- **Namecheap**: Competitive pricing, good management

### 4.2 Configure Cloudflare (Recommended)

Cloudflare provides free DNS, DDoS protection, and SSL:

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) and create a free account
2. Click **Add Site** and enter your domain
3. Select the **Free** plan
4. Cloudflare will scan existing DNS records
5. Add these DNS records:

| Type | Name | Content | Proxy Status | TTL |
|------|------|---------|--------------|-----|
| A | @ (root) | YOUR_SERVER_IP | Proxied | Auto |
| A | api | YOUR_SERVER_IP | Proxied | Auto |
| A | ws | YOUR_SERVER_IP | Proxied | Auto |
| A | sip | YOUR_SERVER_IP | DNS Only | Auto |

6. Note the Cloudflare nameservers provided
7. Update nameservers at your domain registrar
8. Wait 5-30 minutes for DNS propagation
9. In Cloudflare, go to **SSL/TLS** → Set mode to **Full (strict)**

### 4.3 Verify DNS

```bash
# Check A record resolves
dig +short your-domain.com
# Should return your server IP

# Check with specific resolver
dig @1.1.1.1 your-domain.com
```

---

## Step 5: Clone and Configure

### 5.1 Clone Repository

```bash
# SSH into your server
ssh -i ~/.ssh/answerflow-key.pem ubuntu@YOUR_SERVER_IP

# Create directory
mkdir -p /opt/answerflow && cd /opt/answerflow

# Clone repository
git clone https://github.com/your-org/answerflow-ai.git .
```

### 5.2 Create Environment File

```bash
# Copy example
cp .env.example .env

# Generate strong secrets
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
ADMIN_PASSWORD=$(openssl rand -hex 12)

# Write to .env
cat > .env << 'ENVEOF'
# =============================================================================
# Owlbell Configuration
# =============================================================================

# ---------------------------------------------------------------------------
# Domain Configuration
# ---------------------------------------------------------------------------
DOMAIN=your-domain.com
API_SUBDOMAIN=api.your-domain.com
WS_SUBDOMAIN=ws.your-domain.com

# ---------------------------------------------------------------------------
# SSL/TLS
# ---------------------------------------------------------------------------
SSL_EMAIL=admin@your-domain.com
ACME_CA_SERVER=https://acme-v02.api.letsencrypt.org/directory

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=answerflow
POSTGRES_USER=answerflow
POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD
DATABASE_URL=postgresql+asyncpg://answerflow:YOUR_POSTGRES_PASSWORD@postgres:5432/answerflow

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY=YOUR_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# ---------------------------------------------------------------------------
# AI Services
# ---------------------------------------------------------------------------
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
WHISPER_MODEL=large-v3
PIPER_URL=http://piper:5000

# ---------------------------------------------------------------------------
# FreeSWITCH
# ---------------------------------------------------------------------------
FREESWITCH_ESL_HOST=freeswitch
FREESWITCH_ESL_PORT=8021
FREESWITCH_ESL_PASSWORD=ClueCon
SIP_DOMAIN=your-domain.com
EXTERNAL_SIP_PORT=5060
EXTERNAL_RTP_PORT_MIN=10000
EXTERNAL_RTP_PORT_MAX=20000

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@your-domain.com
SMTP_TLS=true

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# ---------------------------------------------------------------------------
# Admin User (created on first startup)
# ---------------------------------------------------------------------------
ADMIN_EMAIL=admin@your-domain.com
ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
ENABLE_PROMETHEUS=true
GRAFANA_ADMIN_PASSWORD=admin

# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------
ENABLE_CALL_RECORDING=true
ENABLE_TRANSCRIPTION=true
ENABLE_CALENDAR_SYNC=true
ENABLE_SMS_NOTIFICATIONS=false
ENABLE_EMAIL_NOTIFICATIONS=false
ENVEOF

# Replace placeholders with generated values
sed -i "s/YOUR_POSTGRES_PASSWORD/$POSTGRES_PASSWORD/g" .env
sed -i "s/YOUR_SECRET_KEY/$SECRET_KEY/g" .env
sed -i "s/YOUR_ADMIN_PASSWORD/$ADMIN_PASSWORD/g" .env

# View the file (secrets are hidden in output)
echo "Admin password: $ADMIN_PASSWORD"
echo "Postgres password: $POSTGRES_PASSWORD"
```

### 5.3 Configure Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 5060/tcp # SIP
sudo ufw allow 5060/udp # SIP
sudo ufw allow 10000:20000/udp # RTP
sudo ufw enable

# Verify
sudo ufw status verbose
```

---

## Step 6: Start Owlbell

### 6.1 First Startup

```bash
cd /opt/answerflow

# Pull images and start in background
docker compose pull
docker compose up -d

# Watch logs to confirm successful startup
docker compose logs -f --tail=50

# You should see:
# - PostgreSQL: "database system is ready"
# - Redis: "Ready to accept connections"
# - FreeSWITCH: "FreeSWITCH Version 1.10.11"
# - Backend: "Uvicorn running on http://0.0.0.0:8000"
# - Frontend: build completing
# - Ollama: "Listening on [::]:11434"
```

### 6.2 Verify Services

```bash
# Check all containers are running
docker compose ps

# Expected output:
# NAME                    STATUS          PORTS
# answerflow-api          Up 2 minutes    0.0.0.0:8000->8000/tcp
# answerflow-dashboard    Up 2 minutes    0.0.0.0:3000->3000/tcp
# answerflow-freeswitch   Up 2 minutes    0.0.0.0:5060->5060/tcp, ...
# answerflow-postgres     Up 2 minutes    5432/tcp
# answerflow-redis        Up 2 minutes    6379/tcp
# answerflow-ollama       Up 2 minutes    11434/tcp
# answerflow-piper        Up 2 minutes    5000/tcp
# answerflow-nginx        Up 2 minutes    0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

### 6.3 Check Health Endpoints

```bash
# Backend health
curl http://localhost:8000/api/v1/health

# Expected: {"status":"ok","version":"0.1.0","services":{"database":"ok","redis":"ok","freeswitch":"ok"}}

# Frontend
curl -I http://localhost

# Expected: HTTP/1.1 200 OK
```

---

## Step 7: Download AI Models

### 7.1 Pull LLM

```bash
# Default: llama3.2:3b (fast, good quality, works on CPU)
docker exec -it answerflow-ollama ollama pull llama3.2:3b

# For better quality (needs more RAM):
# docker exec -it answerflow-ollama ollama pull llama3.2

# Verify
docker exec -it answerflow-ollama ollama list
```

### 7.2 Download Whisper Model

The Whisper model downloads automatically on first use. To pre-download:

```bash
# Enter backend container
docker exec -it answerflow-api bash

# Run Python to trigger download
python -c "
import whisper
model = whisper.load_model('large-v3')
print('Whisper model downloaded')
"

exit
```

### 7.3 Download Piper Voice

Piper voices download automatically. Default voice is included.

```bash
# List available voices
docker exec -it answerflow-piper python -c "
from piper.voice import PiperVoice
import json
print('Piper TTS is ready')
"
```

### 7.4 Test AI Pipeline

```bash
# Enter backend container
docker exec -it answerflow-api bash

# Test LLM
curl -s http://ollama:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Say hello in a friendly, professional manner.",
  "stream": false
}' | python -m json.tool

# Test TTS
curl -s -X POST http://piper:5000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is Owlbell.", "voice": "en_US-lessac-medium"}' \
  --output /tmp/test.wav

# Verify audio file
ls -la /tmp/test.wav

exit
```

---

## Step 8: Access the Dashboard

### 8.1 Open Dashboard

Navigate to `https://your-domain.com` in your browser.

### 8.2 Log In

Use the credentials from your `.env` file:
- **Email**: The `ADMIN_EMAIL` value
- **Password**: The `ADMIN_PASSWORD` value

> **Important**: Change the admin password immediately after first login.

### 8.3 Dashboard Overview

After logging in, you will see:

```
+------------------------------------------------------------------+
|  Owlbell Dashboard                                    [User v]|
+------------------------------------------------------------------+
|  [Dashboard] [Calls] [Messages] [Appointments] [Analytics] [Settings|
+------------------------------------------------------------------+
|                                                                   |
|  +------------------+  +------------------+  +------------------+ |
|  | Active Calls     |  | Today's Calls    |  | Messages         | |
|  |        0         |  |        0         |  |       0          | |
|  |                  |  |                  |  |                  | |
|  +------------------+  +------------------+  +------------------+ |
|                                                                   |
|  +------------------------+  +----------------------------------+ |
|  | Call Volume (7 days)   |  | Recent Activity                  | |
|  |                        |  |                                  | |
|  |    /\      /\          |  | - System started        2m ago   | |
|  |   /  \    /  \    /\   |  | - AI models loaded      1m ago   | |
|  |  /    \  /    \  /  \  |  | - Ready for calls       now      | |
|  | /      \/      \/    \ |  |                                  | |
|  +------------------------+  +----------------------------------+ |
|                                                                   |
+------------------------------------------------------------------+
```

### 8.4 System Status Check

Go to **Settings** → **System Status** to verify all services:

```
Service          Status    Details
-------------------------------------------
Database         OK        PostgreSQL 15.4
Redis            OK        Redis 7.2.0
FreeSWITCH       OK        Version 1.10.11
Ollama           OK        llama3.2:3b loaded
Piper TTS        OK        Ready
Backend API      OK        Version 0.1.0
Frontend         OK        Build 2024.01.15
SSL Certificate  OK        Valid until 2025-04-15
```

---

## Step 9: Configure Your First Tenant

A "tenant" represents one business. Even for a single business, you need one tenant.

### 9.1 Create Tenant

```
Settings → Tenants → New Tenant
```

Fill in:

| Field | Example | Description |
|-------|---------|-------------|
| Business Name | "Smith Family Dental" | Your business name |
| Slug | "smith-dental" | URL-friendly identifier |
| Phone Number | +1-555-123-4567 | Your business phone |
| Timezone | America/New_York | Local timezone |
| Language | en-US | Conversation language |
| Greeting | "Thank you for calling..." | AI opening line |

### 9.2 Set Business Hours

```
Tenant → Business Hours
```

Configure your schedule:

```
Day        Open      Close     Closed
----------------------------------------
Monday     08:00     17:00     [ ]
Tuesday    08:00     17:00     [ ]
Wednesday  08:00     17:00     [ ]
Thursday   08:00     17:00     [ ]
Friday     08:00     16:00     [ ]
Saturday   --        --        [X]
Sunday     --        --        [X]
```

### 9.3 Configure Call Routing

```
Tenant → Call Routing
```

Set up basic routing:

```
When call arrives:
  IF during business hours:
    - Greet caller
    - Ask how we can help
    - Offer: Message, Appointment, or Speak to Human
  
  IF after hours:
    - Inform caller we're closed
    - Offer to take a message
    - Offer to book appointment for next business day
  
  IF emergency keywords ("urgent", "emergency", "pain"):
    - Immediately forward to on-call number
    - If no answer, take detailed message with high priority
```

### 9.4 Configure AI Voice

```
Tenant → AI Configuration
```

| Setting | Options | Recommended |
|---------|---------|-------------|
| Voice | lessac, ljspeech, blizzard | lessac (natural) |
| Speaking Rate | 0.8 - 1.5 | 1.1 (slightly faster) |
| Temperature | 0.0 - 1.0 | 0.7 (balanced) |
| Max Response Length | 50-300 words | 150 |
| Personality | Professional, Friendly, Casual | Friendly |

### 9.5 Save and Activate

Click **Activate Tenant**. The AI is now ready to answer calls for this business.

---

## Step 10: Upload FAQ/Knowledge Base

The knowledge base provides context to the AI so it can answer specific questions about your business.

### 10.1 Prepare Documents

Supported formats:
- **PDF**: Scanned documents (OCR supported), digital PDFs
- **DOCX**: Microsoft Word documents
- **TXT**: Plain text files
- **Markdown**: Markdown files

Best practices:
- One topic per document works better than one giant file
- Use clear headings and structure
- Include specific details (prices, hours, services)
- Avoid scanned images without text layer

### 10.2 Upload Files

```
Tenant → Knowledge Base → Upload Documents
```

Drag and drop files or click to browse. Processing happens automatically:

```
Uploading...    [===========>          ] 50%
Extracting text [================>     ] 75%
Chunking...     [====================>] 100%
Indexing...     [====================>] 100%

Status: Ready (12 chunks indexed)
```

### 10.3 Test Knowledge Base

Use the **Test AI** feature in the dashboard:

```
You (caller): "What are your hours?"
AI: "Our office hours are Monday through Friday, 8 AM to 5 PM, 
     and we're closed on weekends. Is there anything else I can help with?"

You (caller): "Do you take walk-ins?"
AI: "We do accept walk-ins for minor issues, but we recommend 
     scheduling an appointment to minimize your wait time. 
     Would you like me to check our availability?"
```

### 10.4 Monitor AI Performance

```
Tenant → Knowledge Base → Analytics
```

| Metric | Description |
|--------|-------------|
| Documents | Number of uploaded files |
| Total Chunks | Indexed searchable segments |
| Queries Today | How many times AI used KB |
| Confidence Score | Average relevance of responses |

---

## Step 11: Connect Google Calendar

### 11.1 Create Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project: "Owlbell Calendar"
3. Enable the **Google Calendar API**:
   - APIs & Services → Library → Search "Google Calendar API" → Enable

### 11.2 Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Configure consent screen:
   - User Type: **External**
   - App name: "Owlbell"
   - User support email: your email
   - Developer contact: your email
   - Scopes: Add `https://www.googleapis.com/auth/calendar`
   - Test users: Add your email
4. Create OAuth client ID:
   - Application type: **Web application**
   - Name: "Owlbell"
   - Authorized redirect URI: `https://api.your-domain.com/api/v1/calendar/oauth/callback`
5. Click **Create** and note the **Client ID** and **Client Secret**

### 11.3 Configure Owlbell

```
Tenant → Integrations → Google Calendar
```

Paste the credentials:

```
Google Client ID:     123456789-abc123.apps.googleusercontent.com
Google Client Secret: GOCSPX-xxxxxxxxxxxxxxxx
```

Click **Connect** and authorize the application.

### 11.4 Select Calendar

After authorization, select which calendar to use:

```
Available Calendars:
  [X] Primary Calendar (your-email@gmail.com)
  [ ] Work Calendar
  [ ] Shared Staff Calendar

[Save Configuration]
```

### 11.5 Set Availability Rules

```
Tenant → Appointments → Availability
```

| Setting | Value | Description |
|---------|-------|-------------|
| Appointment Duration | 30 minutes | Default slot length |
| Buffer Between | 15 minutes | Gap between appointments |
| Min Advance Notice | 4 hours | Can't book same-hour |
| Max Advance Booking | 30 days | How far ahead |
| Available Days | Mon-Fri | Which days bookable |
| Available Hours | 9:00-17:00 | Booking window |

### 11.6 Test Booking

Call your number and say: *"I'd like to book an appointment for tomorrow at 10 AM."*

The AI will:
1. Check Google Calendar for conflicts
2. Confirm availability
3. Collect your name and reason
4. Create the calendar event
5. Send confirmation SMS (if configured)

Verify in Google Calendar that the event was created.

---

## Step 12: Make Your First Call

### 12.1 Using a SIP Softphone (Free)

Install a SIP softphone on your computer or phone:

**Desktop:**
- [Linphone](https://www.linphone.org/) (Windows, Mac, Linux) -- Free
- [Zoiper](https://www.zoiper.com/) (Windows, Mac, Linux) -- Free tier
- [MicroSIP](https://www.microsip.org/) (Windows) -- Free

**Mobile:**
- Linphone (iOS, Android) -- Free
- Zoiper (iOS, Android) -- Free tier
- Grandstream Wave (iOS, Android) -- Free

### 12.2 Configure Softphone

```
Account/SIP Settings:
  Username: test
  Domain: your-domain.com
  Password: (leave blank for anonymous, or create in FreeSWITCH)
  Transport: UDP
  Port: 5060
```

### 12.3 Create a Test SIP User

```bash
# Enter FreeSWITCH container
docker exec -it answerflow-freeswitch fs_cli

# Create user
freeswitch@answerflow> sofia profile internal flush_inbound_reg

# Add user via XML directory (or use API)
# Exit
/exit
```

Or use the dashboard:

```
Settings → SIP Users → Add User
  Extension: 1001
  Password: (auto-generated)
  Caller ID: Test User
```

### 12.4 Place the Call

1. Open your softphone
2. Register with the credentials
3. Dial your configured number (or extension 1000 for the auto-attendant)
4. Listen for the AI greeting!

### 12.5 Expected Conversation Flow

```
AI: "Thank you for calling Smith Family Dental. This is your 
     AI assistant. How may I help you today?"

You: "I'd like to make an appointment."

AI: "I'd be happy to help you schedule an appointment. What day 
     and time would work best for you?"

You: "Tomorrow at 2 PM."

AI: "Let me check our availability... Yes, we have an opening 
     tomorrow at 2:00 PM. May I have your name, please?"

You: "John Smith."

AI: "Thank you, John. What is the reason for your visit?"

You: "Regular checkup."

AI: "Perfect. I've scheduled your appointment for tomorrow at 
     2:00 PM for a regular checkup. We'll see you then! Is 
     there anything else I can help with?"

You: "No, that's all."

AI: "Thank you for calling Smith Family Dental. Have a wonderful day!"
[Call ends]
```

### 12.6 Verify in Dashboard

After the call:

1. Go to **Dashboard** → you should see the call in recent activity
2. Go to **Calls** → view call details including transcription
3. Go to **Appointments** → verify the booking was created
4. Go to **Messages** → if you left a message, it appears here

---

## Step 13: Configure SIP Trunk (Optional)

For receiving real PSTN calls, you need a SIP trunk provider.

### 13.1 Recommended Providers

| Provider | Monthly Cost | Per-Minute | Notes |
|----------|-------------|------------|-------|
| **Telnyx** | $0 | $0.007/min | Developer-friendly API |
| **Twilio** | $0 | $0.0085/min | Reliable, good docs |
| **Flowroute** | $0 | $0.0059/min | Competitive rates |
| **VoIP.ms** | $0 | $0.005/min | Pay-as-you-go |
| **LocalPhone** | $0 | $0.006/min | Simple setup |

### 13.2 Configure SIP Trunk in FreeSWITCH

Create `/opt/answerflow/infrastructure/freeswitch/conf/sip_profiles/external/telnyx.xml`:

```xml
<include>
  <gateway name="telnyx">
    <param name="realm" value="sip.telnyx.com"/>
    <param name="username" value="YOUR_TELNYX_USERNAME"/>
    <param name="password" value="YOUR_TELNYX_PASSWORD"/>
    <param name="from-domain" value="sip.telnyx.com"/>
    <param name="register" value="true"/>
    <param name="caller-id-in-from" value="true"/>
  </gateway>
</include>
```

Restart FreeSWITCH:

```bash
docker compose restart freeswitch
```

### 13.3 Configure Inbound Route

In the dashboard:

```
Tenant → Phone Numbers → Add Number
  Phone Number: +1-555-123-4567
  Provider: Telnyx
  Route To: AI Agent
  Tenant: smith-dental
```

Or via API:

```bash
curl -X POST https://api.your-domain.com/api/v1/phone-numbers \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+15551234567",
    "provider": "telnyx",
    "route_to": "ai_agent",
    "tenant_id": "your-tenant-id"
  }'
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs -f SERVICE_NAME

# Common issues:
# 1. Port conflict
sudo lsof -i :5060  # Check what's using port 5060

# 2. Permission issues
sudo chown -R $USER:$USER /opt/answerflow

# 3. Memory limit (OOM)
docker stats  # Check memory usage
# Add swap if needed: sudo fallocate -l 4G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

### AI Not Responding

```bash
# Check Ollama
docker exec -it answerflow-ollama ollama list

# If model not loaded:
docker exec -it answerflow-ollama ollama pull llama3.2:3b

# Test Ollama directly:
curl http://localhost:11434/api/generate -d '{"model":"llama3.2:3b","prompt":"Hello","stream":false}'

# Check backend logs:
docker compose logs -f api | grep -i "ollama\|llm\|error"
```

### No Audio in Calls

```bash
# Check FreeSWITCH status
docker exec -it answerflow-freeswitch fs_cli -x "sofia status"

# Check RTP ports are open
sudo ufw status | grep 10000

# Verify codec negotiation
docker exec -it answerflow-freeswitch fs_cli -x "show codecs"

# Check firewall allows RTP
sudo iptables -L | grep 10000
```

### SSL Certificate Issues

```bash
# Check certificate status
docker compose logs certbot

# Force renewal
docker compose run --rm certbot renew --force-renewal

# Test SSL (from another machine)
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

### Database Connection Failures

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Verify connection string in .env matches
grep DATABASE_URL .env

# Test connection manually
docker exec -it answerflow-postgres psql -U answerflow -d answerflow -c "SELECT 1;"
```

### High Latency (Slow AI Responses)

| Symptom | Cause | Solution |
|---------|-------|----------|
| 5-10s delays | CPU-only inference | Use smaller model (3B), add GPU, or add swap |
| Intermittent slowness | Memory pressure | Increase RAM or add swap |
| First call slow | Cold model | Model stays warm while running |
| STT delay | Large audio chunks | Adjust chunk size in settings |

```bash
# Monitor resources
docker stats --no-stream

# Check CPU temperature (if on-premise)
sensors  # May need: sudo apt install lm-sensors
```

---

## Next Steps

Congratulations! Owlbell is now running and handling calls. Here's what to explore next:

### 1. Review Security
- [SECURITY.md](SECURITY.md) -- Harden your installation
- Change default passwords
- Enable two-factor authentication
- Configure firewall rules

### 2. Set Up Monitoring
```
https://your-domain.com/grafana  (admin/admin)
```
Import the included dashboards for:
- Call volume and patterns
- AI response latency
- System resource usage
- Error rates

### 3. Configure Notifications
- Set up SMS via Twilio for urgent messages
- Configure email notifications for daily summaries
- Add webhook endpoints for Slack/Teams

### 4. Optimize AI Performance
- Experiment with different LLM models
- Fine-tune the system prompt for your business
- Upload more knowledge base documents
- Adjust temperature and response length

### 5. Read the Full Documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) -- Understand the system
- [API_REFERENCE.md](API_REFERENCE.md) -- Build integrations
- [DEPLOYMENT.md](DEPLOYMENT.md) -- Production best practices
- [DEVELOPMENT.md](DEVELOPMENT.md) -- Customize the code

### 6. Join the Community
- GitHub Discussions: Ask questions, share tips
- Discord: Real-time community chat
- Report bugs and request features

---

**You are now ready to never miss another business call!**
