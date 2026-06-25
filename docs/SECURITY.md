# Owlbell Security

This document describes the security architecture, features, and practices of Owlbell.

---

## Table of Contents

- [Security Overview](#security-overview)
- [Authentication and Authorization](#authentication-and-authorization)
- [Data Encryption](#data-encryption)
- [Tenant Isolation](#tenant-isolation)
- [Network Security](#network-security)
- [Input Validation](#input-validation)
- [Audit Logging](#audit-logging)
- [Vulnerability Disclosure](#vulnerability-disclosure)
- [Security Checklist](#security-checklist)

---

## Security Overview

Owlbell handles sensitive business communications, including phone call recordings, caller personal information, appointment details, and business data. Security is a foundational design principle, not an afterthought.

### Security Principles

1. **Defense in Depth**: Multiple security layers protect data at every level
2. **Least Privilege**: Components have only the permissions they need
3. **Privacy by Design**: All AI processing is local; no data leaves the server
4. **Zero Trust**: Every request is authenticated and authorized
5. **Full Transparency**: Open source means security can be audited by anyone

### Security Model

```
+----------------------------------------------------------+
|                      INTERNET                             |
+----------------------------------------------------------+
       |                           |
       v                           v
+-------------+           +---------------+
|   Nginx     |           |  Cloudflare   |
|  WAF / SSL  |           |   DDoS / WAF  |
+------+------+           +-------+-------+
       |                           |
       +-------------+-------------+
                     |
                     v
          +----------+----------+
          |   JWT Validation    |
          |   Rate Limiting     |
          |   Input Sanitization|
          +----------+----------+
                     |
                     v
          +----------+----------+
          |  Tenant Isolation   |
          |  RBAC Enforcement   |
          +----------+----------+
                     |
                     v
          +----------+----------+
          |   Encrypted Storage  |
          |   Audit Logging      |
          +----------------------+
```

---

## Authentication and Authorization

### Authentication Methods

| Method | Use Case | Security Level |
|--------|----------|----------------|
| JWT Access Token | Web dashboard, API calls | High |
| JWT Refresh Token | Token renewal | High |
| API Key | Service integrations | High (configurable) |
| SIP Authentication | VoIP clients | Medium |

### JWT Implementation

```python
# Token structure
{
  "sub": "user_uuid",           # Subject (user ID)
  "tenant_id": "tenant_uuid",   # Tenant scope
  "role": "tenant_admin",       # User role
  "jti": "unique_token_id",     # Token identifier (for revocation)
  "iat": 1705689600,            # Issued at
  "exp": 1705693200             # Expiration (60 minutes)
}

# Security measures:
# - HS256 algorithm with 256-bit secret
# - Short-lived access tokens (60 minutes)
# - Refresh token rotation on each use
# - Token blacklist for logout
# - Automatic cleanup of expired tokens
```

### Role-Based Access Control (RBAC)

```
Roles (highest to lowest privilege):

super_admin     -- Full system access, all tenants, all operations
                 -- Can: manage tenants, users, system settings
                 -- Cannot: (nothing)

tenant_admin    -- Full access within their tenant
                 -- Can: configure AI, routing, integrations
                 -- Can: manage tenant users, view all data
                 -- Cannot: access other tenants, system settings

manager         -- Operational access within tenant
                 -- Can: view calls, messages, analytics
                 -- Can: configure business hours, routing rules
                 -- Cannot: manage users, billing, delete tenant

agent           -- Limited operational access
                 -- Can: view calls and messages
                 -- Can: add notes, mark messages as read
                 -- Cannot: configure settings, view analytics

readonly        -- View-only access
                 -- Can: view dashboard, calls, messages
                 -- Cannot: modify anything
```

### Permission System

```python
# Granular permissions
tenant_permissions = [
    "tenant.read",
    "tenant.write",
    "tenant.delete",
]

call_permissions = [
    "calls.read",
    "calls.write",
    "calls.delete",
    "calls.transfer",
    "calls.record",
]

message_permissions = [
    "messages.read",
    "messages.write",
    "messages.delete",
]

# Role-to-permission mapping
ROLE_PERMISSIONS = {
    "super_admin": ["*"],  # All permissions
    "tenant_admin": [
        "tenant.read", "tenant.write",
        "calls.*", "messages.*", "appointments.*",
        "users.*", "routing.*", "knowledge.*",
        "integrations.*", "analytics.*",
    ],
    "manager": [
        "tenant.read",
        "calls.read", "calls.write",
        "messages.read", "messages.write",
        "appointments.*",
        "routing.read", "routing.write",
        "knowledge.read", "knowledge.write",
        "analytics.read",
    ],
    "agent": [
        "tenant.read",
        "calls.read", "calls.write",
        "messages.read", "messages.write",
    ],
    "readonly": [
        "tenant.read",
        "calls.read",
        "messages.read",
        "appointments.read",
    ],
}
```

---

## Data Encryption

### Encryption at Rest

| Data Type | Method | Key Management |
|-----------|--------|----------------|
| Database | PostgreSQL TDE | Transparent, OS-level |
| Call recordings | AES-256-GCM | Per-tenant derived keys |
| Knowledge base docs | AES-256-GCM | Per-tenant derived keys |
| Backups | AES-256-GCM | GPG passphrase |
| Environment secrets | Docker Secrets | Filesystem permissions |

### Encryption in Transit

| Channel | Protocol | Configuration |
|---------|----------|---------------|
| Web/API | HTTPS | TLS 1.3, strong cipher suites |
| WebSocket | WSS | TLS 1.3 |
| SIP | SIP over TLS (SIPS) | TLS 1.2+ |
| Media (RTP) | SRTP (optional) | AES-CM + HMAC-SHA1 |
| ESL | TCP + internal network | Docker network isolation |
| Database | Internal Docker network | No external exposure |
| Redis | Internal Docker network | No external exposure |

### TLS Configuration (Nginx)

```nginx
# TLS 1.3 only, strong ciphers
ssl_protocols TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256;

# HSTS
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'" always;
```

### Secret Management

```bash
# Generate strong secrets
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
ADMIN_PASSWORD=$(openssl rand -hex 16)

# Store in .env with restricted permissions
chmod 600 .env

# Never commit .env to version control
# .gitignore includes .env

# For production, consider Docker Secrets:
echo "$SECRET_KEY" | docker secret create answerflow_secret_key -

# Or use a secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.)
```

---

## Tenant Isolation

### Isolation Strategy: Shared Database, Row-Level Security

All tenants share the same PostgreSQL database, but data is strictly isolated through:

1. **Tenant ID Column**: Every table has a `tenant_id` column
2. **Application-Level Filtering**: All queries automatically include tenant filter
3. **Row-Level Security (RLS)**: PostgreSQL RLS policies as defense in depth

### RLS Policy Implementation

```sql
-- Enable RLS on tenant-scoped tables
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;

-- Create policy: users can only see their tenant's data
CREATE POLICY tenant_isolation_calls ON calls
    USING (tenant_id = current_setting('app.current_tenant')::UUID);

-- Set tenant context before each query
SET app.current_tenant = '550e8400-e29b-41d4-a716-446655440001';
```

### Middleware Implementation

```python
# backend/app/middleware/tenant.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Ensure all queries are scoped to the current tenant."""
    
    async def dispatch(self, request: Request, call_next):
        tenant = getattr(request.state, "tenant", None)
        user = getattr(request.state, "user", None)
        
        if tenant and user:
            # Verify user belongs to this tenant
            if user.tenant_id and user.tenant_id != tenant.id:
                if user.role != "super_admin":
                    raise HTTPException(
                        status_code=403,
                        detail="Tenant isolation violation"
                    )
            
            # Set database tenant context
            request.state.db_tenant_id = str(tenant.id)
        
        return await call_next(request)


# Query helper
async def get_calls(db: AsyncSession, tenant_id: str, **filters):
    """Get calls filtered by tenant with additional filters."""
    query = select(Call).where(
        Call.tenant_id == tenant_id,  # Always tenant-scoped
        **filters
    )
    result = await db.execute(query)
    return result.scalars().all()
```

### Cache Isolation

```python
# Redis keys are prefixed with tenant ID
async def cache_get(tenant_id: str, key: str) -> str:
    prefixed_key = f"tenant:{tenant_id}:{key}"
    return await redis.get(prefixed_key)

async def cache_set(tenant_id: str, key: str, value: str, ttl: int = 300):
    prefixed_key = f"tenant:{tenant_id}:{key}"
    await redis.setex(prefixed_key, ttl, value)
```

### File Storage Isolation

```python
# Uploads stored in per-tenant directories
TENANT_UPLOAD_DIR = "/data/kb/{tenant_id}"

async def save_kb_document(tenant_id: str, file: UploadFile) -> str:
    tenant_dir = Path(TENANT_UPLOAD_DIR.format(tenant_id=tenant_id))
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = tenant_dir / file.filename
    
    # Sanitize filename to prevent directory traversal
    safe_filename = secure_filename(file.filename)
    file_path = tenant_dir / safe_filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return str(file_path)
```

---

## Network Security

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Required ports
sudo ufw allow 22/tcp    # SSH (restrict to your IP in production!)
sudo ufw allow 80/tcp    # HTTP -> redirects to HTTPS
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 5060/tcp  # SIP
sudo ufw allow 5060/udp  # SIP
sudo ufw allow 5061/tcp  # SIPS
sudo ufw allow 10000:20000/udp  # RTP media

# Restrict SSH to specific IP (production)
# sudo ufw allow from YOUR_OFFICE_IP to any port 22

sudo ufw enable
```

### Docker Network Security

```yaml
# docker-compose.yml
services:
  # Public-facing services
  nginx:
    networks:
      - frontend
      - backend
    ports:
      - "80:80"
      - "443:443"
  
  freeswitch:
    networks:
      - frontend  # For SIP/RTP
      - backend   # For ESL
    ports:
      - "5060:5060/udp"
      - "5060:5060/tcp"
      - "10000-20000:10000-20000/udp"
  
  # Internal services (no exposed ports)
  postgres:
    networks:
      - backend
    # NO ports section - only accessible within Docker network
  
  redis:
    networks:
      - backend
  
  api:
    networks:
      - backend
  
  ollama:
    networks:
      - backend

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: false  # backend needs internet for OAuth, webhooks
```

### Fail2Ban Configuration

```bash
# Install fail2ban
sudo apt install fail2ban

# /etc/fail2ban/jail.local
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-http-auth]
enabled = true

[nginx-botsearch]
enabled = true

[nginx-limit-req]
enabled = true

[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

# Custom jail for API brute force
[answerflow-api]
enabled = true
port = 80,443
filter = answerflow-api
logpath = /var/log/answerflow/api.log
maxretry = 10
findtime = 300
bantime = 7200
```

---

## Input Validation

### SQL Injection Prevention

```python
# Safe: Parameterized queries
result = await db.execute(
    select(Call).where(Call.tenant_id == tenant_id, Call.phone_number == phone)
)

# NEVER do this (string formatting):
# query = f"SELECT * FROM calls WHERE phone = '{phone}'"  # VULNERABLE!

# Additional protection: SQLAlchemy ORM
# All queries go through ORM which always parameterizes
```

### XSS Prevention

```python
# All user input is escaped before display
from markupsafe import escape

user_input = "<script>alert('xss')</script>"
safe_input = escape(user_input)  # &lt;script&gt;alert... 

# Pydantic models strip HTML by default
class MessageCreate(BaseModel):
    content: str = Field(..., max_length=2000)
    
    @field_validator("content")
    @classmethod
    def sanitize(cls, v: str) -> str:
        # Remove any HTML tags
        import re
        return re.sub(r'<[^>]+>', '', v)
```

### File Upload Security

```python
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def validate_upload(file: UploadFile) -> None:
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Unsupported file type")
    
    # Check file size
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 50MB)")
    
    # Check magic bytes (verify it's actually the claimed type)
    if not verify_magic_bytes(content, file.content_type):
        raise HTTPException(400, "File content does not match extension")
    
    # Sanitize filename
    safe_name = secure_filename(file.filename)
    
    # Store outside web root
    upload_path = KB_STORAGE_DIR / safe_name
```

### Rate Limiting

```python
# Per-tenant rate limits
RATE_LIMITS = {
    "default": {"requests_per_minute": 60, "requests_per_hour": 3000},
    "auth": {"requests_per_minute": 5, "requests_per_hour": 50},
    "calls": {"requests_per_minute": 120, "requests_per_hour": 5000},
    "webhooks": {"requests_per_minute": 60, "requests_per_hour": 2000},
}

# Redis-backed rate limiting
async def check_rate_limit(
    key: str,
    limit: int,
    window: int  # seconds
) -> bool:
    """Check if request is within rate limit."""
    current = await redis.incr(f"ratelimit:{key}")
    if current == 1:
        await redis.expire(f"ratelimit:{key}", window)
    return current <= limit
```

---

## Audit Logging

### What Gets Logged

| Event | Data Captured | Retention |
|-------|--------------|-----------|
| Login | User ID, IP, timestamp, success/failure | 1 year |
| Logout | User ID, timestamp | 1 year |
| Password change | User ID, timestamp | 1 year |
| API key created | User ID, key name, permissions | 1 year |
| Tenant config change | User ID, changed fields, old/new values | 2 years |
| Call started | Tenant ID, call ID, caller number | 2 years |
| Call ended | Duration, outcome, AI metrics | 2 years |
| Message taken | Tenant ID, message ID, urgency | 2 years |
| Appointment booked | Tenant ID, appointment ID, time | 2 years |
| File uploaded | User ID, file name, size | 1 year |
| Export requested | User ID, export type, record count | 1 year |

### Audit Log Format

```json
{
  "timestamp": "2024-01-20T12:00:00Z",
  "level": "audit",
  "event": "tenant.config_changed",
  "actor": {
    "user_id": "550e8400-e29b-41d4-a716-446655440090",
    "email": "admin@example.com",
    "ip_address": "203.0.113.45",
    "user_agent": "Mozilla/5.0..."
  },
  "resource": {
    "type": "tenant",
    "id": "550e8400-e29b-41d4-a716-446655440001"
  },
  "changes": {
    "ai_config.voice": {
      "old": "en_US-lessac-medium",
      "new": "en_US-ryan-medium"
    }
  },
  "result": "success"
}
```

### Implementation

```python
# backend/app/middleware/audit.py
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class AuditMiddleware(BaseHTTPMiddleware):
    """Log security-relevant events."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Log write operations
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            await log_audit_event(
                event=f"api.{request.method.lower()}",
                request=request,
                response=response
            )
        
        return response


async def log_audit_event(
    event: str,
    request: Request,
    response,
    changes: dict = None
):
    """Write structured audit log entry."""
    user = getattr(request.state, "user", None)
    tenant = getattr(request.state, "tenant", None)
    
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "audit",
        "event": event,
        "actor": {
            "user_id": str(user.id) if user else None,
            "email": user.email if user else None,
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent"),
        },
        "resource": {
            "type": request.path_params.get("resource_type"),
            "id": request.path_params.get("resource_id"),
        },
        "changes": changes,
        "result": "success" if response.status_code < 400 else "failure",
    }
    
    # Write to dedicated audit log file
    audit_logger.info(json.dumps(entry))
```

---

## Vulnerability Disclosure

### Responsible Disclosure Process

We take security seriously and appreciate the efforts of security researchers and users who report vulnerabilities responsibly.

**Please do NOT disclose security issues publicly (GitHub Issues, Discord, etc.).**

### How to Report

| Method | Contact |
|--------|---------|
| **Email** | security@answerflow-ai.com |
| **GPG Key** | [Download public key](https://answerflow-ai.com/security.gpg) |
| **Key ID** | `0x1234ABCD5678EF90` |

### What to Include

1. **Description**: Clear description of the vulnerability
2. **Impact**: What could an attacker achieve?
3. **Steps to Reproduce**: Detailed reproduction steps
4. **Affected Versions**: Which versions are affected?
5. **Suggested Fix**: If you have one (optional)
6. **Your Contact**: How to reach you for follow-up

### Our Commitment

- **Acknowledgment**: Within 48 hours of receiving your report
- **Assessment**: Within 7 days, we'll assess severity and plan a fix
- **Fix Timeline**:
  - Critical: Within 7 days
  - High: Within 30 days
  - Medium: Within 60 days
  - Low: Next scheduled release
- **Disclosure**: We'll work with you on coordinated disclosure
- **Credit**: Public acknowledgment (with your permission)

### Security-Related Bug Bounty

While Owlbell is a free, open-source project, we offer:

- Public acknowledgment in our Security Hall of Fame
- Priority support for your deployment
- Exclusive preview access to new features

### Security Hall of Fame

We gratefully acknowledge the following security researchers:

| Researcher | Date | Issue |
|------------|------|-------|
| *Your name here* | - | - |

---

## Security Checklist

### Pre-Deployment

- [ ] Change all default passwords (admin, FreeSWITCH, Grafana)
- [ ] Generate strong `SECRET_KEY` (32+ random hex characters)
- [ ] Configure firewall (only required ports open)
- [ ] Set up SSL/TLS certificates
- [ ] Enable HSTS
- [ ] Restrict SSH access (key-only, non-root, specific IP if possible)
- [ ] Disable password authentication for SSH
- [ ] Set up fail2ban
- [ ] Configure automatic security updates
- [ ] Remove unnecessary services
- [ ] Enable audit logging

### Ongoing

- [ ] Monitor logs for suspicious activity
- [ ] Review Grafana dashboards regularly
- [ ] Keep Docker images updated
- [ ] Apply security patches promptly
- [ ] Review user access periodically
- [ ] Rotate API keys quarterly
- [ ] Test backup restoration monthly
- [ ] Review fail2ban bans

### Compliance

For businesses requiring specific compliance standards:

| Standard | Status | Notes |
|----------|--------|-------|
| GDPR | Partial | Data stays local, no third-party sharing |
| HIPAA | Self-assess | Business Associate Agreement may be needed |
| SOC 2 | Roadmap | Planned for v0.4.0 |
| PCI DSS | N/A | No payment processing |

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- Security architecture diagrams
- [DEPLOYMENT.md](DEPLOYMENT.md) -- Production hardening steps
- [DEVELOPMENT.md](DEVELOPMENT.md) -- Secure coding practices
