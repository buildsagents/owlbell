# Owlbell Backend — Deployment Guide

Get the FastAPI backend running on any VPS in ~10 minutes.

---

## Prerequisites

- A VPS (Hetzner CPX21 EUR 8.76/mo, DigitalOcean $24/mo, or Oracle Cloud Free)
- Docker + Docker Compose installed
- Your `.env` file ready (all keys configured)

---

## Step 1: SSH into your VPS

```bash
ssh root@YOUR_VPS_IP
```

## Step 2: Install Docker (if not installed)

```bash
curl -fsSL https://get.docker.com | sh
```

## Step 3: Clone the repo

```bash
git clone https://github.com/YOUR_ORG/owlbell.git /opt/owlbell
cd /opt/owlbell
```

Or upload via SCP:
```bash
scp -r /path/to/project root@YOUR_VPS_IP:/opt/owlbell
```

## Step 4: Upload your .env

```bash
scp /path/to/project/.env root@YOUR_VPS_IP:/opt/owlbell/.env
```

## Step 5: Build and start

```bash
cd /opt/owlbell
docker compose -f docker-compose.api.yml up -d --build
```

## Step 6: Verify it's running

```bash
docker compose -f docker-compose.api.yml logs api
curl http://localhost:8000/health
```

You should see: `{"status":"ok"}`

---

## Updating

```bash
cd /opt/owlbell
git pull
docker compose -f docker-compose.api.yml up -d --build
```

## Viewing Logs

```bash
docker compose -f docker-compose.api.yml logs -f api
```

## Restarting

```bash
docker compose -f docker-compose.api.yml restart api
```

## Stopping

```bash
docker compose -f docker-compose.api.yml down
```

---

## DNS Setup (after backend is running)

Point your API subdomain to the VPS IP:

| Type | Name | Value |
|------|------|-------|
| A | api | YOUR_VPS_IP |

Then set up SSL with Certbot or use Cloudflare proxy.

---

## SSL with Cloudflare (Recommended)

1. Add A record: `api` → `YOUR_VPS_IP`
2. Enable Cloudflare proxy (orange cloud)
3. SSL/TLS mode: **Full (Strict)**
4. Done — HTTPS is automatic

---

## Troubleshooting

**Container won't start:**
```bash
docker compose -f docker-compose.api.yml logs api
```

**Database connection error:**
- Verify `DATABASE_URL` in `.env` points to Supabase
- Check Supabase project is active at app.supabase.com

**Port 80/443 already in use:**
```bash
sudo lsof -i :80
sudo kill <PID>
```

**Out of memory (4GB VPS):**
- Remove monitoring services or upgrade VPS
- The API alone needs ~512MB
