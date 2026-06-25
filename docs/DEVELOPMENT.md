# Owlbell Development Guide

Guide for developers who want to contribute to Owlbell or customize it for their needs.

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Running Locally](#running-locally)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Git Workflow](#git-workflow)
- [Adding New Integrations](#adding-new-integrations)
- [AI Model Customization](#ai-model-customization)

---

## Development Environment Setup

### Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Backend language |
| Node.js | 20+ | Frontend runtime |
| npm | 10+ | Package manager |
| Docker | 25+ | Services (DB, Redis, FreeSWITCH) |
| Docker Compose | 2.27+ | Orchestration |
| Git | 2.40+ | Version control |
| Make | 4.3+ | Build automation (optional) |

### Repository Structure

```
answerflow-ai/
├── backend/                    # Python backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI application entry
│   │   ├── config.py          # Configuration management
│   │   ├── database.py        # SQLAlchemy setup
│   │   ├── auth/              # Authentication
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # Auth endpoints
│   │   │   ├── service.py     # Auth business logic
│   │   │   ├── models.py      # Auth DB models
│   │   │   ├── schemas.py     # Pydantic schemas
│   │   │   └── dependencies.py # JWT validation
│   │   ├── tenants/           # Tenant management
│   │   ├── calls/             # Call handling
│   │   ├── messages/          # Message management
│   │   ├── appointments/      # Appointment booking
│   │   ├── knowledge/         # Knowledge base
│   │   ├── routing/           # Call routing
│   │   ├── users/             # User management
│   │   ├── analytics/         # Analytics & reporting
│   │   ├── integrations/      # External integrations
│   │   ├── ai/                # AI pipeline
│   │   │   ├── whisper.py     # STT client
│   │   │   ├── ollama.py      # LLM client
│   │   │   ├── piper.py       # TTS client
│   │   │   └── pipeline.py    # Orchestration
│   │   ├── telephony/         # FreeSWITCH integration
│   │   │   ├── esl_client.py  # ESL connection
│   │   │   ├── call_session.py # Call state machine
│   │   │   ├── audio_pipeline.py # Audio I/O
│   │   │   └── vad.py         # Voice activity detection
│   │   ├── ws/                # WebSocket handlers
│   │   ├── tasks/             # Celery background tasks
│   │   └── utils/             # Shared utilities
│   ├── migrations/            # Alembic migrations
│   ├── tests/                 # Test suite
│   ├── Dockerfile
│   ├── requirements.txt       # Production deps
│   ├── requirements-dev.txt   # Development deps
│   └── pyproject.toml         # Tool config
├── dashboard/                  # React frontend
│   ├── src/
│   │   ├── main.tsx           # Entry point
│   │   ├── App.tsx            # Root component
│   │   ├── api/               # API client
│   │   ├── components/        # Reusable components
│   │   ├── pages/             # Page components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── stores/            # State management
│   │   ├── types/             # TypeScript types
│   │   └── utils/             # Utilities
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── infrastructure/             # Infrastructure configs
│   ├── nginx/
│   ├── freeswitch/
│   ├── prometheus/
│   └── grafana/
├── docs/                       # Documentation
├── scripts/                    # Utility scripts
├── docker-compose.yml
├── docker-compose.override.yml
├── .env.example
├── .gitignore
└── Makefile
```

### Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/answerflow-ai.git
cd answerflow-ai

# 2. Set up Python backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cd ..

# 3. Set up frontend
cd dashboard
npm install
cd ..

# 4. Copy environment
cp .env.example .env

# 5. Start infrastructure services
docker compose up -d postgres redis freeswitch

# 6. Run migrations
cd backend
alembic upgrade head
cd ..

# 7. Create test data (optional)
cd backend
python -c "
import asyncio
from app.initial_data import init_db
asyncio.run(init_db())
"
cd ..
```

---

## Running Locally

### Start Backend

```bash
cd backend
source venv/bin/activate

# Development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using the provided script
python -m app.main
```

Backend will be available at `http://localhost:8000`.

Auto-generated docs: `http://localhost:8000/docs` (Swagger UI)

### Start Frontend

```bash
cd dashboard

# Development server
npm run dev

# Frontend available at http://localhost:5173
```

### Start Celery Worker (for background tasks)

```bash
cd backend
source venv/bin/activate

celery -A app.tasks worker -l info -Q default,notifications

# Or with beat scheduler for periodic tasks
celery -A app.tasks worker -l info -B
```

### Start AI Services

```bash
# Start Ollama (in Docker)
docker compose up -d ollama

# Pull model (first time)
docker exec -it answerflow-ollama ollama pull llama3.2:3b

# Start Piper TTS
docker compose up -d piper
```

### Full Development Stack

```bash
# Terminal 1: Infrastructure
docker compose up -d postgres redis freeswitch ollama piper

# Terminal 2: Backend API
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Terminal 3: Celery Worker
cd backend && source venv/bin/activate && celery -A app.tasks worker -l info

# Terminal 4: Frontend
cd dashboard && npm run dev

# Terminal 5: WebSocket test server (optional)
cd backend && source venv/bin/activate && python -m app.ws.server
```

### Makefile Shortcuts

```bash
# Start all services
make up

# Start backend only
make backend

# Start frontend only
make frontend

# Run tests
make test

# Run linting
make lint

# Run formatting
make format

# Full quality check
make check
```

---

## Running Tests

### Test Structure

```
backend/tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_auth.py
│   ├── test_tenants.py
│   ├── test_calls.py
│   ├── test_messages.py
│   ├── test_appointments.py
│   ├── test_knowledge.py
│   └── test_ai_pipeline.py
├── integration/             # Integration tests
│   ├── test_api_flows.py
│   ├── test_call_lifecycle.py
│   ├── test_calendar_sync.py
│   └── test_websocket.py
└── fixtures/               # Test data
    ├── sample_audio.wav
    ├── sample_kb.pdf
    └── mock_responses.py
```

### Running Tests

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -xvs

# Run specific test file
pytest tests/unit/test_auth.py -xvs

# Run specific test
pytest tests/unit/test_auth.py::test_login_success -xvs

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run integration tests only
pytest tests/integration/ -xvs

# Run with marker
pytest -m "not slow"  # Skip slow tests
pytest -m "slow"      # Run only slow tests
```

### Coverage Report

```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

### Test Configuration

```ini
# backend/pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -xvs --tb=short
env =
    DATABASE_URL=postgresql+asyncpg://answerflow:test@localhost:5432/answerflow_test
    REDIS_URL=redis://localhost:6379/1
    SECRET_KEY=test-secret-key
    ENVIRONMENT=test

markers =
    slow: marks tests as slow (deselect with -m "not slow")
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

### Writing Tests

```python
# Example test: backend/tests/unit/test_auth.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.anyio
async def test_login_success(async_client: AsyncClient):
    """Test successful login returns JWT tokens."""
    response = await async_client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "test_password"
    })
    
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.anyio
async def test_login_invalid_credentials(async_client: AsyncClient):
    """Test login with wrong password returns 401."""
    response = await async_client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrong_password"
    })
    
    assert response.status_code == 401


# Fixtures in conftest.py
import pytest_asyncio
from app.database import async_session_maker

@pytest_asyncio.fixture
async def async_client():
    """Create async test client."""
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client(async_client: AsyncClient):
    """Create authenticated test client."""
    response = await async_client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "admin_password"
    })
    token = response.json()["data"]["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    yield async_client
```

---

## Code Style

### Python

We use **Black**, **Ruff**, and **mypy** for code quality.

#### Configuration (pyproject.toml)

```toml
[tool.black]
line-length = 88
target-version = ["py311"]
include = "backend/app/.*\\.py$"

[tool.ruff]
line-length = 88
target-version = "py311"
select = ["E", "F", "I", "W", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.pydocstyle]
convention = "google"

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

#### Running Linters

```bash
cd backend

# Format with Black
black app/ tests/

# Lint with Ruff
ruff check app/ tests/ --fix

# Type check with mypy
mypy app/

# All at once
make lint
```

#### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black
        language_version: python3.11
        
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix]
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### TypeScript / Frontend

```bash
cd dashboard

# Lint
npm run lint

# Type check
npm run type-check

# Format
npm run format

# All
npm run check
```

### Code Guidelines

#### Python

```python
# Use type hints everywhere
from typing import Optional, List

def get_user_by_email(email: str) -> Optional[User]:
    ...

# Use async/await for I/O operations
async def fetch_calls(tenant_id: str) -> List[Call]:
    async with async_session() as session:
        result = await session.execute(
            select(Call).where(Call.tenant_id == tenant_id)
        )
        return result.scalars().all()

# Use Pydantic for validation
class CreateCallRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")
    caller_name: Optional[str] = Field(None, max_length=100)
    
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return v.strip().replace(" ", "").replace("-", "")

# Use dependency injection
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    ...
```

---

## Git Workflow

### Branch Naming

```
feature/description        # New features
fix/description            # Bug fixes
docs/description           # Documentation updates
refactor/description       # Code refactoring
test/description           # Test additions
chore/description          # Maintenance tasks
```

### Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Build, tooling, dependency changes
- `perf`: Performance improvements

Examples:
```
feat(calls): add call transfer capability

fix(ai): resolve race condition in STT pipeline

docs(api): update webhook documentation with examples

refactor(auth): extract JWT logic into separate service

test(integrations): add Google Calendar sync tests

chore(deps): update SQLAlchemy to 2.0.30
```

### Pull Request Process

1. **Create a branch**: `git checkout -b feature/my-feature`
2. **Make changes** with clear commits
3. **Add tests** for new functionality
4. **Run quality checks**: `make check`
5. **Update documentation** if needed
6. **Push and create PR** with detailed description
7. **Address review comments**
8. **Merge** once approved and CI passes

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
```

---

## Adding New Integrations

Owlbell supports integrations via a plugin-like architecture. Here's how to add a new integration (e.g., Microsoft Outlook Calendar).

### 1. Define the Integration Interface

```python
# backend/app/integrations/base.py
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime


class CalendarIntegration(ABC):
    """Base class for calendar integrations."""
    
    name: str
    slug: str
    
    @abstractmethod
    async def check_availability(
        self, 
        date: datetime,
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Return available time slots for a given date."""
        ...
    
    @abstractmethod
    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee: dict
    ) -> str:
        """Create calendar event, return event ID."""
        ...
    
    @abstractmethod
    async def delete_event(self, event_id: str) -> bool:
        """Delete calendar event."""
        ...
```

### 2. Implement the Integration

```python
# backend/app/integrations/outlook_calendar.py
import httpx
from datetime import datetime
from typing import List

from .base import CalendarIntegration
from app.config import settings


class OutlookCalendarIntegration(CalendarIntegration):
    """Microsoft Outlook Calendar integration."""
    
    name = "Microsoft Outlook Calendar"
    slug = "outlook_calendar"
    
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client = httpx.AsyncClient(
            base_url=self.GRAPH_API_BASE,
            headers={"Authorization": f"Bearer {access_token}"}
        )
    
    async def check_availability(
        self,
        date: datetime,
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Check availability using Microsoft Graph API."""
        start = date.replace(hour=0, minute=0)
        end = date.replace(hour=23, minute=59)
        
        response = await self.client.post(
            "/me/calendar/getSchedule",
            json={
                "schedules": ["me"],
                "startTime": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                "endTime": {"dateTime": end.isoformat(), "timeZone": "UTC"},
                "availabilityViewInterval": str(duration_minutes)
            }
        )
        response.raise_for_status()
        
        data = response.json()
        # Parse availability and return free slots
        return self._parse_availability(data, duration_minutes)
    
    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee: dict
    ) -> str:
        """Create event in Outlook calendar."""
        event_data = {
            "subject": title,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "attendees": [{
                "emailAddress": {
                    "address": attendee.get("email", ""),
                    "name": attendee.get("name", "")
                },
                "type": "required"
            }]
        }
        
        response = await self.client.post("/me/events", json=event_data)
        response.raise_for_status()
        
        return response.json()["id"]
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete event from Outlook calendar."""
        response = await self.client.delete(f"/me/events/{event_id}")
        return response.status_code == 204
    
    def _parse_availability(self, data: dict, duration: int) -> List[TimeSlot]:
        """Parse Microsoft availability response into time slots."""
        # Implementation...
        pass
```

### 3. Register the Integration

```python
# backend/app/integrations/registry.py
from .google_calendar import GoogleCalendarIntegration
from .outlook_calendar import OutlookCalendarIntegration

CALENDAR_INTEGRATIONS = {
    "google_calendar": GoogleCalendarIntegration,
    "outlook_calendar": OutlookCalendarIntegration,
}


def get_calendar_integration(slug: str, credentials: dict):
    """Get calendar integration by slug."""
    integration_class = CALENDAR_INTEGRATIONS.get(slug)
    if not integration_class:
        raise ValueError(f"Unknown calendar integration: {slug}")
    return integration_class(**credentials)
```

### 4. Add API Endpoints

```python
# backend/app/integrations/router.py
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

@router.post("/outlook-calendar/connect")
async def connect_outlook_calendar(
    request: OutlookConnectRequest,
    current_user: User = Depends(get_current_user)
):
    """Initiate Outlook Calendar OAuth flow."""
    # Implement Microsoft OAuth
    auth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?..."
    return {"auth_url": auth_url}


@router.post("/outlook-calendar/callback")
async def outlook_calendar_callback(
    request: OutlookCallbackRequest,
    current_user: User = Depends(get_current_user)
):
    """Handle Outlook OAuth callback."""
    # Exchange code for token, store credentials
    ...
```

### 5. Add Frontend Support

```typescript
// dashboard/src/pages/Integrations/OutlookCalendarConnect.tsx
import { useState } from 'react';
import { api } from '@/api/client';

export function OutlookCalendarConnect() {
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = async () => {
    setIsConnecting(true);
    const response = await api.post('/integrations/outlook-calendar/connect');
    window.location.href = response.data.auth_url;
  };

  return (
    <div className="integration-card">
      <h3>Microsoft Outlook Calendar</h3>
      <p>Sync appointments with Outlook Calendar</p>
      <button 
        onClick={handleConnect}
        disabled={isConnecting}
        className="btn-primary"
      >
        {isConnecting ? 'Connecting...' : 'Connect Outlook'}
      </button>
    </div>
  );
}
```

### 6. Add Tests

```python
# backend/tests/integration/test_outlook_calendar.py
import pytest
from unittest.mock import AsyncMock, patch
from app.integrations.outlook_calendar import OutlookCalendarIntegration


@pytest.mark.anyio
async def test_outlook_check_availability():
    """Test availability checking with Outlook."""
    integration = OutlookCalendarIntegration(access_token="test_token")
    
    with patch.object(integration.client, "post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=AsyncMock(return_value={
                "value": [{
                    "availabilityView": "000002220000000000000022"
                }]
            })
        )
        
        slots = await integration.check_availability(
            datetime(2024, 1, 22), 
            duration_minutes=30
        )
        
        assert len(slots) > 0
        mock_post.assert_called_once()
```

---

## AI Model Customization

### Using Different LLM Models

Owlbell supports any model compatible with Ollama:

```bash
# List available models
docker exec -it answerflow-ollama ollama list

# Pull a different model
docker exec -it answerflow-ollama ollama pull llama3.1:8b   # Better quality
docker exec -it answerflow-ollama ollama pull mistral:7b      # Alternative
docker exec -it answerflow-ollama ollama pull phi3:3.8b       # Microsoft model
docker exec -it answerflow-ollama ollama pull gemma:4b        # Google model

# Update .env
OLLAMA_MODEL=llama3.1:8b

# Restart API
docker compose restart api
```

### Customizing the System Prompt

The system prompt defines the AI's personality and behavior:

```python
# backend/app/ai/prompts.py

DEFAULT_SYSTEM_PROMPT = """You are {ai_name}, the AI receptionist for {business_name}.

YOUR ROLE:
- Greet callers warmly and professionally
- Answer questions using the provided knowledge base
- Take messages when requested
- Book appointments when appropriate
- Route urgent calls to human staff

PERSONALITY: {personality}
LANGUAGE: {language}

RULES:
- Keep responses concise (under {max_words} words)
- Ask one question at a time
- Confirm actions before taking them
- Be polite but efficient
- If unsure, offer to take a message
- NEVER make up information not in the knowledge base
- NEVER share internal contact information unless explicitly configured

CURRENT CONTEXT:
- Time: {current_time}
- Business hours: {business_hours}
- Today's schedule: {schedule_summary}
"""

def build_system_prompt(tenant: Tenant) -> str:
    """Build customized system prompt for a tenant."""
    ai_config = tenant.ai_config
    
    return DEFAULT_SYSTEM_PROMPT.format(
        ai_name=ai_config.get("name", "the virtual assistant"),
        business_name=tenant.name,
        personality=ai_config.get("personality", "friendly and professional"),
        language=tenant.language,
        max_words=ai_config.get("max_response_length", 150),
        current_time=datetime.now(tenant.timezone).strftime("%I:%M %p"),
        business_hours=format_business_hours(tenant.business_hours),
        schedule_summary=get_today_schedule_summary(tenant.id)
    )
```

### Fine-tuning for Specific Industries

```python
# Dental office prompt
DENTAL_PROMPT = """You are the receptionist for a dental practice.

SERVICES YOU CAN DISCUSS:
- Regular cleanings and checkups
- Fillings and cavities
- Root canals
- Extractions
- Cosmetic dentistry (whitening, veneers)
- Emergency dental care

APPOINTMENT TYPES:
- Cleaning: 45-60 minutes
- Consultation: 30 minutes
- Emergency: As soon as possible
- Follow-up: Per dentist recommendation

INSURANCE QUESTIONS:
- Direct callers to the billing department for specific questions
- You can confirm we accept most major insurance plans
"""

# Legal office prompt
LEGAL_PROMPT = """You are the receptionist for a law office.

IMPORTANT RULES:
- Do NOT provide legal advice
- Do NOT discuss case details
- Schedule consultations only
- Collect caller name, contact, and general matter type
- Maintain strict confidentiality

MATTER TYPES:
- Family law
- Criminal defense
- Personal injury
- Estate planning
- Business law

INITIAL CONSULTATIONS:
- Duration: 30-60 minutes
- Fee: Discussed at consultation
- Preparation: Bring relevant documents
"""
```

### Optimizing STT Performance

```python
# backend/app/ai/whisper.py
from faster_whisper import WhisperModel

# CPU-optimized
model = WhisperModel(
    "large-v3",
    device="cpu",
    compute_type="int8",  # Quantized for faster CPU inference
    cpu_threads=4,
    num_workers=2,
)

# GPU-optimized
model = WhisperModel(
    "large-v3",
    device="cuda",
    compute_type="float16",  # Half precision for GPU
)

# Stream processing for lower latency
segments, info = model.transcribe(
    audio_buffer,
    language="en",
    vad_filter=True,           # Filter out non-speech
    vad_parameters={
        "min_silence_duration_ms": 800,  # End speech after 800ms silence
        "speech_pad_ms": 400             # Pad speech segments
    },
    beam_size=5,               # Faster than default beam size
    best_of=5,
    condition_on_previous_text=True,
)
```

### Custom TTS Voice

```bash
# Download additional Piper voices
cd /opt/answerflow/data/piper-voices

# Available voices:
# en_US-lessac-medium (default, female)
# en_US-ryan-medium (male)
# en_US-libritts-high (higher quality)
# en_GB-southern_male-medium (British)

# Download
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json

# Update config
docker exec -it answerflow-api python -c "
from app.config import settings
settings.tts_voice = 'en_US-ryan-medium'
"
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture overview
- [API_REFERENCE.md](API_REFERENCE.md) -- API documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) -- Production deployment
- [SECURITY.md](SECURITY.md) -- Security guidelines
