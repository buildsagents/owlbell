# Running Owlbell locally (zero infrastructure)

This runs the full stack on your machine with **no Docker, PostgreSQL, or Redis
install required**:

- **PostgreSQL** is provided by the pip package [`pgserver`](https://pypi.org/project/pgserver/),
  which bundles a real Postgres binary and runs it on a local port. Data lives in
  `backend/.pgdata/`.
- **Redis** is replaced by an in-process [`fakeredis`](https://pypi.org/project/fakeredis/)
  server (enabled via `USE_FAKE_REDIS=1`).
- The heavy AI stack (Whisper / Ollama / Piper / Torch) and FreeSWITCH telephony
  are **not** required to boot; they degrade gracefully and the AI pipeline is
  disabled locally via `FEATURE_ENABLE_AI_GREETING=false`.

## Prerequisites
- Python 3.11 (a venv already exists at `backend/.venv`)
- Node 18+ / npm (dashboard deps already installed)

## 1. Backend — http://localhost:8000

```bash
cd project/backend
./.venv/Scripts/python.exe run_local.py
```

`run_local.py` starts bundled Postgres, creates all tables, and serves the API.

- Health:   http://localhost:8000/health
- API docs: http://localhost:8000/docs   (Swagger UI)
- OpenAPI:  http://localhost:8000/openapi.json  (81 routes)

First-time setup of the venv (only if it is missing):

```bash
cd project/backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev-lite.txt pgserver
```

## 2. Frontend — http://localhost:5173

```bash
cd project/dashboard
npm install      # first time only
npm run dev
```

Vite proxies `/api` and `/ws` to the backend on port 8000, so the dashboard
talks to the API with no extra config. `dashboard/.env` already points
`VITE_API_URL` at `http://localhost:8000`.

## Smoke test

```bash
# Register a business owner (writes to Postgres)
curl -X POST http://localhost:8000/api/v1/auth/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@demobiz.com","password":"DemoPass123!","business_name":"Demo Biz","phone_number":"+15551234567","timezone":"America/New_York"}'

# Log in (reads from Postgres, returns JWT tokens)
curl -X POST http://localhost:8000/api/v1/auth/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@demobiz.com","password":"DemoPass123!"}'
```

## Notes / expected (non-error) conditions
- **This is a development bring-up, not production.** The dev secrets in
  `run_local.py` and trust-auth Postgres are local-only.
- FreeSWITCH shows `unreachable` and AI shows `not_initialized` in `/health` —
  expected, since those subsystems are intentionally not run locally (no SIP
  server; AI disabled via `FEATURE_ENABLE_AI_GREETING=false`). `/health` therefore
  reports `degraded` while `database`, `redis`, `event_bus`, and `celery` report
  `ok`. Startup is otherwise clean (no ERROR log lines).
- `get_current_user` in `backend/api/dependencies.py` is still a placeholder that
  returns a mock user, so `GET /api/v1/auth/auth/me` returns `user@example.com`
  rather than the logged-in user. It returns 200 — wiring real JWT decoding is a
  follow-up, not a bug.
- Data persists across **clean** restarts (Ctrl+C). A hard kill (SIGKILL) of the
  launcher can drop the embedded Postgres data — stop with Ctrl+C.

## Fixes applied to make the app build & run error-free
Backend:
- `db/models/business.py`, `db/models/operations.py`: 5 UUID columns used a
  SQLAlchemy type as the `Mapped[...]` annotation without an explicit column type
  (rejected by SQLAlchemy 2.0). Added explicit `PgUUID(as_uuid=True)`.
- `db/cache/client.py`: `get_redis_client()` uses `fakeredis` when `USE_FAKE_REDIS`.
- `PyJWT` added to `requirements-dev-lite.txt` (token code imports `jwt`).
- `main.py`: event-bus subscriptions used `await event_bus.subscribe(type, cb)`
  (wrong — that's an async-generator consumer). Switched to `event_bus.on(...)`
  and mapped to real `EventType` members.
- `operations/admin/routes.py`: added the missing `APIRouter` (`admin_router` /
  `router`) exposing `AdminService` at `/api/v1/ops/admin/*` (was skipped at boot).
- `config.py`: `protected_namespaces=()` on `WhisperSettings` (silences the
  `model_size` pydantic warning).
- `api/dependencies.py`: `UserContext.to_profile()` passed `created_at=None` into a
  required datetime (caused `/me` to 500); now uses `datetime.utcnow()`.

Dashboard (`npm run build` was fully broken):
- Removed ~25 unused imports/vars; added `src/vite-env.d.ts`; removed a bogus
  `nav-items` import in `lib/constants.ts`; de-duplicated `PlanType`
  (`types/billing.ts` now imports it from `./auth`); fixed null-safety in
  `pages/settings/ai-personality.tsx`; installed `@radix-ui/react-avatar`.
- `src/index.css`: migrated from Tailwind v3 `@tailwind` directives to v4
  `@import "tailwindcss"; @config "../tailwind.config.ts";` (the project uses
  Tailwind v4, which broke on `border-border`). `npm run build` now passes and
  the backend serves the built SPA from `dashboard/dist`.
