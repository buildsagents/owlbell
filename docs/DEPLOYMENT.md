# Owlbell Deployment Guide

Complete guide for deploying Owlbell to production environments, from zero-budget options to enterprise-grade setups.

---

## Table of Contents

- [Hosting Options](#hosting-options)
- [Docker Compose Deployment](#docker-compose-deployment)
- [SSL/TLS Setup](#ssltls-setup)
- [Environment Variables](#environment-variables)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Backup and Restore](#backup-and-restore)
- [Updating to New Versions](#updating-to-new-versions)
- [Troubleshooting](#troubleshooting)

---

## Hosting Options

### Comparison Matrix

| Provider | Monthly Cost | CPU | RAM | Storage | Network | GPU | Best For |
|----------|-------------|-----|-----|---------|---------|-----|----------|
| Oracle Cloud Free | $0 | 4 ARM | 24GB | 200GB | 10TB | No | Budget-conscious |
| Hetzner CPX21 | EUR 8.76 | 4 AMD | 8GB | 80GB | 20TB | No | Best value |
| Hetzner CPX31 | EUR 15.72 | 4 AMD | 16GB | 160GB | 20TB | No | Comfortable budget |
| Hetzner CCX23 | EUR 31.51 | 4 Intel | 16GB | 160GB | 20TB | No | Business use |
| DigitalOcean 8GB | $24 | 4 Intel | 8GB | 160GB | 5TB | No | Simple setup |
| Self-hosted | Electricity | Varies | Varies | Varies | Home | Optional | Privacy paranoid |

### Oracle Cloud Always Free (Recommended for $0)

#### Step 1: Create Account
1. Visit [cloud.oracle.com](https://cloud.oracle.com)
2. Sign up with email, password, and credit card (for verification only -- never charged for free tier)
3. Complete phone verification
4. Wait for account activation (usually instant, sometimes up to 24 hours)

#### Step 2: Create VM Instance

```
Navigation: Compute → Instances → Create Instance

Name: answerflow-server
Compartment: (root)
Placement: AD-1
Image: Canonical Ubuntu 24.04
Shape: VM.Standard.A1.Flex (ARM processor)
OCPU: 4
Memory: 24GB
Boot Volume: 100GB
Networking: Create new VCN
SSH Keys: Upload your public key or generate new
```

#### Step 3: Configure Network

```
VCN → Security Lists → Default Security List → Add Ingress Rules:

Rule 1:  0.0.0.0/0  TCP  22      (SSH)
Rule 2:  0.0.0.0/0  TCP  80      (HTTP)
Rule 3:  0.0.0.0/0  TCP  443     (HTTPS)
Rule 4:  0.0.0.0/0  TCP  5060    (SIP)
Rule 5:  0.0.0.0/0  UDP  5060    (SIP)
Rule 6:  0.0.0.0/0  TCP  5061    (SIPS)
Rule 7:  0.0.0.0/0  TCP  8021    (ESL)
Rule 8:  0.0.0.0/0  UDP  10000-20000 (RTP)
```

> **Important**: Oracle Cloud requires opening ports in both Security Lists AND Network Security Groups.

#### Step 4: Connect and Setup

```bash
ssh -i ~/.ssh/your-key ubuntu@YOUR_INSTANCE_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker (see Step 3 in GETTING_STARTED.md)
# Then continue with Docker Compose deployment below
```

### Hetzner Cloud (Best Value)

#### Step 1: Create Account
1. Visit [hetzner.com/cloud](https://www.hetzner.com/cloud/)
2. Sign up and verify email
3. Add payment method (credit card or PayPal)

#### Step 2: Create Server

```
Project: (create new)
Name: answerflow-server
Type: Shared vCPU (CPX21 recommended)
Location: Falkenstein or Nuremberg (EU), Ashburn (US)
Image: Ubuntu 24.04
Networking: IPv4 enabled, IPv6 enabled
Firewalls: Create new firewall
SSH Key: Add your public key
```

#### Step 3: Configure Firewall

```
Firewall Rules:
  Inbound:
    TCP 22    from Anywhere     (SSH)
    TCP 80    from Anywhere     (HTTP)
    TCP 443   from Anywhere     (HTTPS)
    TCP 5060  from Anywhere     (SIP)
    UDP 5060  from Anywhere     (SIP)
    TCP 5061  from Anywhere     (SIPS)
    UDP 10000-20000 from Anywhere (RTP)
  Outbound:
    Any       to Anywhere
```

#### Step 4: Connect

```bash
ssh -i ~/.ssh/your-key root@YOUR_SERVER_IP

# Hetzner servers are ready to go
# Install Docker and deploy
```

### Self-Hosted / On-Premise

#### Requirements

- Static public IP address (or dynamic DNS service)
- Port forwarding capability on router
- Uninterrupted power (UPS recommended)

#### Network Setup

```
Internet → Router (port forward) → Server (Docker)

Router Configuration:
  - Port Forward TCP 80    → Server:80
  - Port Forward TCP 443   → Server:443
  - Port Forward UDP 5060  → Server:5060
  - Port Forward TCP 5060  → Server:5060
  - Port Forward UDP 10000-20000 → Server:10000-20000
```

#### Dynamic DNS (if no static IP)

```bash
# Install ddclient
sudo apt install ddclient

# Configure for DuckDNS
# /etc/ddclient.conf:
protocol=duckdns, \
login=token, \
password=YOUR_DUCKDNS_TOKEN \
your-domain.duckdns.org
```

---

## Docker Compose Deployment

### Project Structure

```
/opt/answerflow/
├── docker-compose.yml          # Main orchestration
├── docker-compose.prod.yml     # Production overrides
├── docker-compose.override.yml # Local development overrides
├── .env                        # Environment configuration
├── .env.example                # Example configuration
├── backend/                    # Backend source
│   ├── Dockerfile
│   └── app/
├── dashboard/                  # Frontend source
│   ├── Dockerfile
│   └── src/
├── infrastructure/             # Infrastructure configs
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── ssl/
│   ├── freeswitch/
│   │   └── conf/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── provisioning/
└── data/                       # Persistent data
    ├── postgres/
    ├── recordings/
    ├── kb/
    └── backups/
```

### Production Docker Compose

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  nginx:
    image: nginx:1.26-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infrastructure/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./infrastructure/nginx/ssl:/etc/nginx/ssl:ro
      - ./data/certbot/conf:/etc/letsencrypt:ro
      - ./data/certbot/www:/var/www/certbot:ro
    depends_on:
      - api
      - dashboard
    restart: unless-stopped
    networks:
      - answerflow

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - OLLAMA_URL=${OLLAMA_URL}
      - OLLAMA_MODEL=${OLLAMA_MODEL}
      - PIPER_URL=${PIPER_URL}
    volumes:
      - ./data/recordings:/app/data/recordings
      - ./data/kb:/app/data/kb
    depends_on:
      - postgres
      - redis
      - ollama
      - piper
    restart: unless-stopped
    networks:
      - answerflow
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    environment:
      - VITE_API_URL=https://api.${DOMAIN}
      - VITE_WS_URL=wss://ws.${DOMAIN}
    restart: unless-stopped
    networks:
      - answerflow

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.tasks worker -l info -Q default,notifications,calendar
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - C_FORCE_ROOT=true
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    networks:
      - answerflow
    deploy:
      resources:
        limits:
          memory: 1G

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./infrastructure/postgres/init:/docker-entrypoint-initdb.d
    restart: unless-stopped
    networks:
      - answerflow
    deploy:
      resources:
        limits:
          memory: 1G

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - ./data/redis:/data
    restart: unless-stopped
    networks:
      - answerflow

  freeswitch:
    image: answerflow/freeswitch:1.10.11
    ports:
      - "5060:5060/tcp"
      - "5060:5060/udp"
      - "5061:5061/tcp"
      - "10000-20000:10000-20000/udp"
    volumes:
      - ./infrastructure/freeswitch/conf:/etc/freeswitch:ro
      - ./data/recordings:/var/lib/freeswitch/recordings
    restart: unless-stopped
    networks:
      - answerflow
    deploy:
      resources:
        limits:
          memory: 512M

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ./data/ollama:/root/.ollama
    restart: unless-stopped
    networks:
      - answerflow
    deploy:
      resources:
        limits:
          memory: 6G
    # Uncomment for NVIDIA GPU:
    # runtime: nvidia
    # environment:
    #   - NVIDIA_VISIBLE_DEVICES=all

  piper:
    image: answerflow/piper:latest
    restart: unless-stopped
    networks:
      - answerflow

  prometheus:
    image: prom/prometheus:v2.53
    volumes:
      - ./infrastructure/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./data/prometheus:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped
    networks:
      - answerflow

  grafana:
    image: grafana/grafana:11.0
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_INSTALL_PLUGINS=grafana-clock-panel
    volumes:
      - ./infrastructure/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./data/grafana:/var/lib/grafana
    restart: unless-stopped
    networks:
      - answerflow

  # Uncomment for automatic SSL:
  # certbot:
  #   image: certbot/certbot:latest
  #   volumes:
  #     - ./data/certbot/conf:/etc/letsencrypt
  #     - ./data/certbot/www:/var/www/certbot
  #   entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h; done'"

networks:
  answerflow:
    driver: bridge
```

### Deploy Commands

```bash
cd /opt/answerflow

# 1. Pull latest images
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

# 2. Start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Verify all running
docker compose ps

# 4. Check logs
docker compose logs -f --tail=50

# 5. Download AI models
docker exec -it answerflow-ollama ollama pull llama3.2:3b

# 6. Run migrations
docker exec -it answerflow-api alembic upgrade head

# 7. Create initial admin user
docker exec -it answerflow-api python -c "
from app.initial_data import init_db
import asyncio
asyncio.run(init_db())
"

# 8. Verify health
curl -s http://localhost/api/v1/health | python -m json.tool
```

---

## SSL/TLS Setup

### Option 1: Let's Encrypt (Recommended for Production)

#### Using Certbot with Nginx

```bash
# Install certbot on host
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --standalone -d your-domain.com -d api.your-domain.com -d ws.your-domain.com

# Certificates will be at:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem

# Copy to project
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/answerflow/infrastructure/nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/answerflow/infrastructure/nginx/ssl/
sudo chown -R $USER:$USER /opt/answerflow/infrastructure/nginx/ssl/

# Set up auto-renewal
echo "0 3 * * * root certbot renew --quiet --deploy-hook 'docker compose -f /opt/answerflow/docker-compose.yml -f /opt/answerflow/docker-compose.prod.yml exec -T nginx nginx -s reload'" | sudo tee /etc/cron.d/certbot-renewal
```

#### Using Docker Certbot

```bash
# Run certbot container
docker run -it --rm \
  -v /opt/answerflow/data/certbot/conf:/etc/letsencrypt \
  -v /opt/answerflow/data/certbot/www:/var/www/certbot \
  -p 80:80 \
  certbot/certbot certonly \
  --standalone \
  -d your-domain.com \
  -d api.your-domain.com \
  --agree-tos \
  --email admin@your-domain.com

# Add to docker-compose for auto-renewal
# (already included in docker-compose.prod.yml, uncomment certbot service)
```

### Option 2: Cloudflare Origin Certificates

If using Cloudflare proxy, use origin certificates for encryption between Cloudflare and your server:

```
Cloudflare Dashboard → SSL/TLS → Origin Server → Create Certificate:
  - Let Cloudflare generate private key
  - Save as: /opt/answerflow/infrastructure/nginx/ssl/cloudflare-origin.pem
  - Save key as: /opt/answerflow/infrastructure/nginx/ssl/cloudflare-origin.key
```

Nginx config:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/cloudflare-origin.pem;
    ssl_certificate_key /etc/nginx/ssl/cloudflare-origin.key;
    
    # Only accept connections from Cloudflare IPs
    # (configure allow/deny rules)
}
```

### Option 3: Self-Signed Certificates (Local/Testing Only)

```bash
cd /opt/answerflow/infrastructure/nginx/ssl

# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate
openssl req -new -x509 -sha256 -key server.key -out server.crt -days 365 \
  -subj "/C=US/ST=State/L=City/O=Owlbell/OU=IT/CN=your-domain.com"

# Combine for some services
cat server.crt server.key > server.pem
```

### Option 4: ZeroSSL (Free Alternative to Let's Encrypt)

```bash
# Using acme.sh client
curl https://get.acme.sh | sh
~/.acme.sh/acme.sh --issue -d your-domain.com --nginx
```

---

## Environment Variables

### Complete Reference

#### Domain and SSL

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOMAIN` | Yes | -- | Primary domain name |
| `API_SUBDOMAIN` | No | `api.{DOMAIN}` | API subdomain |
| `WS_SUBDOMAIN` | No | `ws.{DOMAIN}` | WebSocket subdomain |
| `SSL_EMAIL` | Yes | -- | Email for SSL certificate notifications |
| `ACME_CA_SERVER` | No | Let's Encrypt | ACME server URL |

#### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_HOST` | No | `postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `POSTGRES_DB` | No | `answerflow` | Database name |
| `POSTGRES_USER` | No | `answerflow` | Database user |
| `POSTGRES_PASSWORD` | Yes | -- | Database password (strong) |
| `DATABASE_URL` | No | Auto-built | Full connection string |

#### Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_HOST` | No | `redis` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_URL` | No | Auto-built | Full connection string |

#### Security

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | -- | JWT signing key (32+ chars hex) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime |

#### AI Services

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_URL` | No | `http://ollama:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | No | `llama3.2:3b` | Default LLM model |
| `WHISPER_MODEL` | No | `large-v3` | Whisper STT model |
| `PIPER_URL` | No | `http://piper:5000` | Piper TTS endpoint |

#### FreeSWITCH

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FREESWITCH_ESL_HOST` | No | `freeswitch` | ESL hostname |
| `FREESWITCH_ESL_PORT` | No | `8021` | ESL port |
| `FREESWITCH_ESL_PASSWORD` | No | `ClueCon` | ESL password |
| `SIP_DOMAIN` | No | `{DOMAIN}` | SIP domain |
| `EXTERNAL_SIP_PORT` | No | `5060` | External SIP port |
| `EXTERNAL_RTP_PORT_MIN` | No | `10000` | Min RTP port |
| `EXTERNAL_RTP_PORT_MAX` | No | `20000` | Max RTP port |

#### Notifications

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | No | -- | SMTP server host |
| `SMTP_PORT` | No | `587` | SMTP server port |
| `SMTP_USER` | No | -- | SMTP username |
| `SMTP_PASSWORD` | No | -- | SMTP password |
| `SMTP_FROM` | No | `noreply@{DOMAIN}` | From email address |
| `SMTP_TLS` | No | `true` | Use TLS for SMTP |
| `TWILIO_ACCOUNT_SID` | No | -- | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | No | -- | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | No | -- | Twilio phone number |

#### Admin User

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ADMIN_EMAIL` | Yes | -- | Initial admin email |
| `ADMIN_PASSWORD` | Yes | -- | Initial admin password |

#### Monitoring

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_PROMETHEUS` | No | `true` | Enable metrics collection |
| `GRAFANA_ADMIN_PASSWORD` | No | `admin` | Grafana admin password |

#### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_CALL_RECORDING` | No | `true` | Record calls |
| `ENABLE_TRANSCRIPTION` | No | `true` | Transcribe calls |
| `ENABLE_CALENDAR_SYNC` | No | `true` | Sync with Google Calendar |
| `ENABLE_SMS_NOTIFICATIONS` | No | `false` | Send SMS notifications |
| `ENABLE_EMAIL_NOTIFICATIONS` | No | `false` | Send email notifications |

---

## Monitoring and Alerting

### Prometheus Metrics

Prometheus collects metrics at `http://localhost:9090`.

Available metrics:

```
# Call metrics
answerflow_calls_total{direction, status, tenant}
answerflow_call_duration_seconds{tenant}
answerflow_active_calls{tenant}

# AI pipeline metrics
answerflow_stt_latency_seconds
answerflow_llm_latency_seconds
answerflow_tts_latency_seconds
answerflow_ai_errors_total{stage}

# API metrics
http_requests_total{method, endpoint, status}
http_request_duration_seconds{endpoint}

# System metrics
process_cpu_seconds_total
process_resident_memory_bytes

# Database metrics
db_connections_active{database}
db_query_duration_seconds
```

### Grafana Dashboards

Grafana runs at `https://your-domain.com/grafana` (admin/password from `.env`).

Pre-configured dashboards:

| Dashboard | Path | Description |
|-----------|------|-------------|
| System Overview | `dashboards/system.json` | CPU, RAM, disk, network |
| Call Analytics | `dashboards/calls.json` | Call volume, duration, outcomes |
| AI Performance | `dashboards/ai.json` | STT/LLM/TTS latency and errors |
| API Metrics | `dashboards/api.json` | Request rates, response times |
| Database | `dashboards/database.json` | Connection pool, query times |

### Alerting Rules (Prometheus)

```yaml
# infrastructure/prometheus/alerts.yml
groups:
  - name: answerflow
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: AILatencyHigh
        expr: answerflow_llm_latency_seconds > 10
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "AI response latency exceeds 10 seconds"

      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space below 10%"

      - alert: FreeSWITCHDown
        expr: up{job="freeswitch"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "FreeSWITCH is down -- calls cannot be received"

      - alert: MissedCallsSpike
        expr: rate(answerflow_calls_total{status="missed"}[1h]) > 5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High rate of missed calls"
```

### Setting Up Alerts

```bash
# Add alertmanager to docker-compose
# Configure Slack/PagerDuty/Email notifications
# See: infrastructure/prometheus/alertmanager.yml
```

### Log Aggregation

```bash
# View all service logs
docker compose logs -f

# View specific service
docker compose logs -f api --tail=100

# View with filter
docker compose logs api | grep ERROR

# Export logs for debugging
docker compose logs > /tmp/answerflow-logs-$(date +%Y%m%d).txt
```

---

## Backup and Restore

### Automated Daily Backups

```bash
#!/bin/bash
# /opt/answerflow/scripts/backup.sh
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_ROOT="/opt/answerflow/backups"
BACKUP_DIR="$BACKUP_ROOT/$DATE"
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "[$DATE] Starting backup..."

# 1. Database backup
echo "Backing up PostgreSQL..."
docker exec answerflow-postgres pg_dump \
  -U answerflow \
  -h localhost \
  answerflow | gzip > "$BACKUP_DIR/database.sql.gz"

# 2. Call recordings
echo "Backing up recordings..."
if [ -d "/opt/answerflow/data/recordings" ]; then
  tar czf "$BACKUP_DIR/recordings.tar.gz" -C /opt/answerflow/data recordings/
fi

# 3. Knowledge base documents
echo "Backing up knowledge base..."
if [ -d "/opt/answerflow/data/kb" ]; then
  tar czf "$BACKUP_DIR/kb.tar.gz" -C /opt/answerflow/data kb/
fi

# 4. Configuration
echo "Backing up configuration..."
cp /opt/answerflow/.env "$BACKUP_DIR/env_backup"
cp -r /opt/answerflow/infrastructure "$BACKUP_DIR/infrastructure"

# 5. Ollama models list
docker exec answerflow-ollama ollama list > "$BACKUP_DIR/ollama-models.txt"

# 6. Create manifest
cat > "$BACKUP_DIR/MANIFEST.txt" << EOF
Owlbell Backup
Date: $DATE
Version: $(docker exec answerflow-api python -c "import app; print(app.__version__)" 2>/dev/null || echo "unknown")
Size: $(du -sh "$BACKUP_DIR" | cut -f1)
EOF

# 7. Encrypt backup
echo "Encrypting backup..."
tar czf - "$BACKUP_DIR" | gpg --symmetric --cipher-algo AES256 --batch --passphrase "$BACKUP_ENCRYPTION_KEY" > "$BACKUP_DIR.tar.gz.gpg"

# 8. Upload to remote storage (configure rclone)
if command -v rclone &> /dev/null; then
  echo "Uploading to remote storage..."
  rclone copy "$BACKUP_DIR.tar.gz.gpg" remote:answerflow-backups/
fi

# 9. Cleanup old backups
echo "Cleaning up old backups..."
find "$BACKUP_ROOT" -name "*.gpg" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_ROOT" -type d -empty -delete

# 10. Verify backup
if [ -f "$BACKUP_DIR.tar.gz.gpg" ]; then
  echo "Backup completed: $BACKUP_DIR.tar.gz.gpg"
  echo "Backup size: $(du -sh "$BACKUP_DIR.tar.gz.gpg" | cut -f1)"
else
  echo "Backup FAILED!" >&2
  exit 1
fi

# Cleanup unencrypted files
rm -rf "$BACKUP_DIR"
```

### Setup Cron

```bash
chmod +x /opt/answerflow/scripts/backup.sh

# Add to crontab
crontab -e

# Run daily at 3 AM
0 3 * * * /opt/answerflow/scripts/backup.sh >> /var/log/answerflow-backup.log 2>&1
```

### Restore from Backup

```bash
#!/bin/bash
# restore.sh - Restore from backup
set -euo pipefail

BACKUP_FILE="$1"  # Path to .tar.gz.gpg file
ENCRYPTION_KEY="$2"

# 1. Decrypt
echo "Decrypting backup..."
gpg --decrypt --batch --passphrase "$ENCRYPTION_KEY" "$BACKUP_FILE" | tar xzf -

BACKUP_DIR=$(tar tzf <(gpg --decrypt --batch --passphrase "$ENCRYPTION_KEY" "$BACKUP_FILE" 2>/dev/null) | head -1 | cut -d/ -f1)

# 2. Stop services
cd /opt/answerflow
docker compose stop api worker

# 3. Restore database
echo "Restoring database..."
gunzip < "$BACKUP_DIR/database.sql.gz" | docker exec -i answerflow-postgres psql -U answerflow

# 4. Restore recordings
echo "Restoring recordings..."
if [ -f "$BACKUP_DIR/recordings.tar.gz" ]; then
  tar xzf "$BACKUP_DIR/recordings.tar.gz" -C /opt/answerflow/data/
fi

# 5. Restore KB documents
echo "Restoring knowledge base..."
if [ -f "$BACKUP_DIR/kb.tar.gz" ]; then
  tar xzf "$BACKUP_DIR/kb.tar.gz" -C /opt/answerflow/data/
fi

# 6. Restore configuration
echo "Restoring configuration..."
cp "$BACKUP_DIR/env_backup" /opt/answerflow/.env

# 7. Start services
echo "Starting services..."
docker compose start api worker

# 8. Verify
echo "Verifying..."
sleep 5
curl -s http://localhost/api/v1/health | python -m json.tool

echo "Restore complete!"
```

---

## Updating to New Versions

### Standard Update Procedure

```bash
cd /opt/answerflow

# 1. Create backup first
./scripts/backup.sh

# 2. Check current version
git describe --tags

# 3. Fetch latest
git fetch origin

# 4. See what's new
git log HEAD..origin/main --oneline

# 5. Read changelog
cat CHANGELOG.md | head -100

# 6. Pull updates
git pull origin main

# 7. Review configuration changes
diff .env .env.example

# 8. Update environment if needed
nano .env

# 9. Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 10. Run migrations
docker exec -it answerflow-api alembic upgrade head

# 11. Verify
curl -s http://localhost/api/v1/health
docker compose ps

# 12. Check logs for errors
docker compose logs --tail=50
```

### Rollback Procedure

If something goes wrong:

```bash
cd /opt/answerflow

# 1. Stop services
docker compose down

# 2. Restore database from backup
# (Use restore.sh with pre-update backup)

# 3. Checkout previous version
git checkout PREVIOUS_TAG

# 4. Rebuild
docker compose build --no-cache
docker compose up -d

# 5. Verify
curl -s http://localhost/api/v1/health
```

### Version Pinning

For stability, pin to specific versions:

```yaml
# docker-compose.prod.yml
services:
  api:
    image: answerflow/api:v0.1.0  # Pin version
    # instead of building from source
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Services won't start

```bash
# Check for port conflicts
sudo lsof -i :80
sudo lsof -i :443
sudo lsof -i :5060
sudo lsof -i :5432
sudo lsof -i :6379

# Check disk space
df -h

# Check memory
free -h

# View specific service logs
docker compose logs SERVICE_NAME
```

#### Issue: Can't connect to FreeSWITCH

```bash
# Check FreeSWITCH status
docker exec answerflow-freeswitch fs_cli -x "status"

# Check ESL connection
docker exec answerflow-freeswitch fs_cli -x "show api"

# Verify network connectivity
docker exec answerflow-api nc -zv freeswitch 8021

# Restart FreeSWITCH
docker compose restart freeswitch
```

#### Issue: AI responses are very slow (>10 seconds)

```bash
# Check CPU usage
top

# Check if model is loaded
docker exec answerflow-ollama ollama ps

# Try smaller model
docker exec answerflow-ollama ollama pull llama3.2:3b

# Check swap usage
free -h

# Add more swap if needed
sudo fallocate -l 8G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### Issue: No audio in calls

```bash
# Check codec negotiation
docker exec answerflow-freeswitch fs_cli -x "show calls"

# Check RTP ports
sudo ufw status | grep 10000

# Test with fs_cli
docker exec answerflow-freeswitch fs_cli -x "originate user/1000 &playback(/tmp/test.wav)"

# Check firewall
sudo iptables -L | grep -i udp
```

#### Issue: SSL certificate errors

```bash
# Check certificate
echo | openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates

# Force renew
docker compose run --rm certbot renew --force-renewal
docker compose restart nginx

# Check nginx config
docker compose exec nginx nginx -t
```

#### Issue: Database connection errors

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres | tail -50

# Test connection
docker exec -it answerflow-postgres psql -U answerflow -d answerflow -c "SELECT 1;"

# Check connection string in .env matches
grep DATABASE_URL .env
```

#### Issue: WebSocket not connecting

```bash
# Check WebSocket endpoint is accessible
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: $(openssl rand -base64 16)" \
  https://ws.your-domain.com/api/v1/health

# Check nginx WebSocket configuration
docker compose exec nginx nginx -T | grep -i websocket

# Check logs
docker compose logs api | grep -i websocket
```

### Getting Help

If you can't resolve an issue:

1. Check logs: `docker compose logs --tail=200 > /tmp/debug.log`
2. Check system resources: `top`, `free -h`, `df -h`
3. Run health check: `curl http://localhost/api/v1/health`
4. Gather info and ask in GitHub Discussions or Discord

---

## Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) -- First-time setup
- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture
- [DEVELOPMENT.md](DEVELOPMENT.md) -- Development environment
- [SECURITY.md](SECURITY.md) -- Security hardening
