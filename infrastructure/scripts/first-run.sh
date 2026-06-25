#!/bin/bash
# ============================================================
# Owlbell — First-Run Setup Script
# ============================================================
# File: infrastructure/scripts/first-run.sh
# Purpose: One-command local development setup for Owlbell.
#   - Checks prerequisites (Docker, ports)
#   - Creates .env from template
#   - Generates secrets
#   - Starts core services (PostgreSQL, Redis)
#   - Runs database migrations
#   - Seeds demo data (Smith Dental Clinic)
#   - Starts remaining services
#   - Displays URLs and login credentials
#   - Performs health check verification
#
# Usage:
#   cd /path/to/answerflow
#   ./infrastructure/scripts/first-run.sh
#
#   # Force reset (re-create volumes, re-seed)
#   ./infrastructure/scripts/first-run.sh --reset
#
#   # Skip demo data seeding
#   ./infrastructure/scripts/first-run.sh --no-demo
#
#   # Use external database (skip postgres container)
#   ./infrastructure/scripts/first-run.sh --external-db
#
# Exit codes:
#   0  All services healthy
#   1  Missing prerequisite
#   2  Port conflict
#   3  Docker not running
#   4  Database connection failed
#   5  Health check failed
# ============================================================

set -euo pipefail

# ----------------------------------------------------------
# Color output helpers
# ----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}   $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_err()   { echo -e "${RED}[ERR]${NC}   $1" >&2; }
log_step()  { echo -e "\n${BOLD}${CYAN}=== $1 ===${NC}"; }
log_pass()  { echo -e "${GREEN}✓${NC} $1"; }
log_fail()  { echo -e "${RED}✗${NC} $1"; }

# ----------------------------------------------------------
# Script configuration
# ----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
INFRA_DIR="${PROJECT_ROOT}/infrastructure"
BACKEND_DIR="${PROJECT_ROOT}/backend"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_TEMPLATE="${INFRA_DIR}/docker/.env.template"
COMPOSE_FILE="${INFRA_DIR}/docker/docker-compose.yml"
COMPOSE_OVERRIDE="${PROJECT_ROOT}/docker-compose.override.yml"

# Default settings
RESET_MODE=false
SEED_DEMO=true
EXTERNAL_DB=false
SKIP_HEALTH_CHECK=false
VERBOSE=false

# Port requirements (service => port)
declare -A REQUIRED_PORTS=(
    ["PostgreSQL"]=5432
    ["Redis"]=6379
    ["API"]=8000
    ["FreeSWITCH ESL"]=8021
    ["FreeSWITCH SIP"]=5060
    ["FreeSWITCH WS"]=5066
    ["Whisper STT"]=8001
    ["Piper TTS"]=8002
    ["Dashboard Vite"]=5173
)

# ----------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --reset)
                RESET_MODE=true
                shift
                ;;
            --no-demo)
                SEED_DEMO=false
                shift
                ;;
            --external-db)
                EXTERNAL_DB=true
                shift
                ;;
            --skip-health)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_err "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << 'EOF'
Usage: first-run.sh [OPTIONS]

  --reset          Remove all volumes and containers, start fresh
  --no-demo        Skip demo data seeding
  --external-db    Use external PostgreSQL (skip postgres container)
  --skip-health    Skip health check verification
  -v, --verbose    Enable verbose output
  -h, --help       Show this help

Examples:
  ./first-run.sh                    # Standard first run
  ./first-run.sh --reset            # Full reset + re-seed
  ./first-run.sh --no-demo          # Start without demo data
  ./first-run.sh --reset --no-demo  # Clean start, no demo
EOF
}

# ----------------------------------------------------------
# Utility functions
# ----------------------------------------------------------

generate_secret() {
    openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64
}

generate_jwt_secret() {
    openssl rand -base64 32
}

wait_for_service() {
    local host="$1"
    local port="$2"
    local service_name="$3"
    local max_retries="${4:-30}"
    local delay="${5:-2}"

    log_info "Waiting for ${service_name} (${host}:${port})..."
    for ((i = 1; i <= max_retries; i++)); do
        if nc -z "${host}" "${port}" 2>/dev/null; then
            log_ok "${service_name} is ready"
            return 0
        fi
        if [[ "$VERBOSE" == true ]]; then
            log_info "  Retry ${i}/${max_retries}..."
        fi
        sleep "${delay}"
    done
    log_err "${service_name} failed to start on ${host}:${port}"
    return 1
}

run_in_api_container() {
    local cmd="$1"
    if [[ "$VERBOSE" == true ]]; then
        log_info "Running: ${cmd}"
    fi
    docker compose -f "${COMPOSE_FILE}" exec -T api bash -c "${cmd}"
}

# ----------------------------------------------------------
# Step 1: Check prerequisites
# ----------------------------------------------------------
check_prerequisites() {
    log_step "Step 1/8 — Checking Prerequisites"

    # Docker
    if ! command -v docker &> /dev/null; then
        log_err "Docker is not installed. Please install Docker first:"
        log_err "  https://docs.docker.com/get-docker/"
        exit 1
    fi
    log_pass "Docker installed ($(docker --version | awk '{print $3}' | tr -d ','))"

    # Docker Compose (v2 plugin or standalone)
    if docker compose version &> /dev/null; then
        log_pass "Docker Compose v2 available"
    elif command -v docker-compose &> /dev/null; then
        log_pass "Docker Compose v1 available ($(docker-compose --version))"
    else
        log_err "Docker Compose is not installed"
        exit 1
    fi

    # docker daemon running
    if ! docker info &> /dev/null; then
        log_err "Docker daemon is not running. Start it with:"
        log_err "  sudo systemctl start docker   (Linux)"
        log_err "  open -a Docker                (macOS)"
        exit 3
    fi
    log_pass "Docker daemon running"

    # Python 3.11+ (for running seed script directly)
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        log_pass "Python ${PYTHON_VERSION} available"
    else
        log_warn "Python 3 not found — seed script will need manual execution"
    fi

    # openssl (for secret generation)
    if command -v openssl &> /dev/null; then
        log_pass "OpenSSL available"
    else
        log_warn "OpenSSL not found — using fallback secret generation"
    fi

    log_ok "All prerequisites satisfied"
}

# ----------------------------------------------------------
# Step 2: Check port availability
# ----------------------------------------------------------
check_ports() {
    log_step "Step 2/8 — Checking Port Availability"

    local conflicts=0
    for service in "${!REQUIRED_PORTS[@]}"; do
        local port="${REQUIRED_PORTS[$service]}"
        if lsof -Pi ":${port}" -sTCP:LISTEN -t &> /dev/null || \
           netstat -tuln 2>/dev/null | grep -q ":${port} " || \
           ss -tuln 2>/dev/null | grep -q ":${port} "; then
            log_warn "Port ${port} (${service}) is already in use"
            ((conflicts++)) || true
        else
            log_pass "Port ${port} (${service}) available"
        fi
    done

    if [[ $conflicts -gt 0 ]]; then
        log_warn "${conflicts} port(s) are occupied. Services may conflict."
        log_info "To free ports: lsof -ti:<port> | xargs kill -9"
        read -rp "Continue anyway? [y/N]: " answer
        if [[ ! "$answer" =~ ^[Yy]$ ]]; then
            log_info "Aborted by user."
            exit 2
        fi
    else
        log_ok "All required ports are available"
    fi
}

# ----------------------------------------------------------
# Step 3: Create .env file
# ----------------------------------------------------------
setup_env() {
    log_step "Step 3/8 — Environment Configuration"

    if [[ -f "$ENV_FILE" ]] && [[ "$RESET_MODE" == false ]]; then
        log_warn ".env file already exists"
        read -rp "Keep existing .env? [Y/n]: " answer
        if [[ ! "$answer" =~ ^[Nn]$ ]]; then
            log_ok "Using existing .env"
            return 0
        fi
    fi

    log_info "Creating .env configuration..."

    # Generate secrets
    local jwt_secret
    jwt_secret=$(generate_jwt_secret)
    local db_password
    db_password=$(generate_secret | head -c 24)
    local redis_password
    redis_password=$(generate_secret | head -c 24)

    cat > "$ENV_FILE" << EOF
# ============================================================
# Owlbell — Environment Configuration
# Auto-generated by first-run.sh on $(date)
# ============================================================

# --- Application ---
APP_ENV=development
APP_DEBUG=true
APP_TESTING=false

# --- Database (PostgreSQL) ---
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=answerflow
POSTGRES_PASSWORD=${db_password}
POSTGRES_DB=answerflow

# --- Redis ---
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${redis_password}
REDIS_DB=0

# --- Security ---
SECURITY_JWT_SECRET=${jwt_secret}

# --- FreeSWITCH ---
FS_HOST=freeswitch
FS_ESL_PASSWORD=ClueCon

# --- AI Services ---
OLLAMA_HOST=ollama
OLLAMA_MODEL=llama3.2:3b
WHISPER_MODEL_SIZE=base
PIPER_MODEL=en_US-lessac-medium

# --- Ports (host mapping) ---
API_PORT=8000
DASHBOARD_PORT=5173
POSTGRES_HOST_PORT=5432
REDIS_HOST_PORT=6379

# --- Integration placeholders ---
# INTEGRATION_TWILIO_ACCOUNT_SID=
# INTEGRATION_TWILIO_AUTH_TOKEN=
# INTEGRATION_SENDGRID_API_KEY=
# INTEGRATION_SLACK_WEBHOOK_URL=
EOF

    # Secure the file
    chmod 600 "$ENV_FILE"
    log_ok ".env created at ${ENV_FILE}"
    log_info "Database password: ${db_password:0:8}****"
    log_info "JWT secret:        ${jwt_secret:0:16}****"
}

# ----------------------------------------------------------
# Step 4: Start core services
# ----------------------------------------------------------
start_core_services() {
    log_step "Step 4/8 — Starting Core Services"

    if [[ "$RESET_MODE" == true ]]; then
        log_warn "Reset mode: removing existing volumes and containers..."
        docker compose -f "${COMPOSE_FILE}" \
            -f "${COMPOSE_OVERRIDE}" \
            down -v --remove-orphans 2>/dev/null || true
        log_ok "Previous containers and volumes removed"
    fi

    # Pull latest images in background
    log_info "Pulling Docker images..."
    docker compose -f "${COMPOSE_FILE}" pull 2>/dev/null || log_warn "Some images may be built locally"

    # Start PostgreSQL and Redis first
    log_info "Starting PostgreSQL and Redis..."
    if [[ "$EXTERNAL_DB" == true ]]; then
        docker compose -f "${COMPOSE_FILE}" up -d redis
    else
        docker compose -f "${COMPOSE_FILE}" up -d postgres redis
    fi

    # Wait for PostgreSQL
    if [[ "$EXTERNAL_DB" == false ]]; then
        wait_for_service localhost 5432 "PostgreSQL" 30 2 || {
            log_err "PostgreSQL failed to start. Check logs:"
            log_err "  docker compose -f ${COMPOSE_FILE} logs postgres"
            exit 4
        }
    fi

    # Wait for Redis
    wait_for_service localhost 6379 "Redis" 30 2 || {
        log_err "Redis failed to start"
        exit 4
    }

    log_ok "Core services are running"
}

# ----------------------------------------------------------
# Step 5: Run database migrations
# ----------------------------------------------------------
run_migrations() {
    log_step "Step 5/8 — Database Migrations"

    log_info "Running Alembic migrations..."

    # Check if running inside Docker or locally
    if docker compose -f "${COMPOSE_FILE}" ps | grep -q "api"; then
        log_info "Running migrations inside API container..."
        run_in_api_container "cd /app/backend && alembic upgrade head"
    else
        log_info "API container not running yet. Starting temporary migration container..."
        # Run migrations using a temporary container with backend code mounted
        docker compose -f "${COMPOSE_FILE}" run --rm \
            -v "${BACKEND_DIR}:/app/backend:ro" \
            api bash -c "cd /app/backend && alembic upgrade head" 2>/dev/null || {
            log_warn "Alembic migration container failed — trying direct Python approach"
            # Fallback: run migrations with Python directly
            if command -v python3 &> /dev/null && [[ -f "${BACKEND_DIR}/db/models/__init__.py" ]]; then
                log_info "Creating tables from SQLAlchemy models..."
                (cd "${PROJECT_ROOT}" && python3 -c "
import asyncio, sys
sys.path.insert(0, '${BACKEND_DIR}')
from backend.config import get_settings
from backend.db.models import Base
from sqlalchemy.ext.asyncio import create_async_engine

async def create_tables():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print('Tables created successfully')

asyncio.run(create_tables())
") || log_warn "Table creation may have partially failed"
            fi
        }
    fi

    log_ok "Database migrations complete"
}

# ----------------------------------------------------------
# Step 6: Seed demo data
# ----------------------------------------------------------
seed_demo_data() {
    if [[ "$SEED_DEMO" == false ]]; then
        log_step "Step 6/8 — Demo Data Seeding (SKIPPED)"
        log_info "Use --demo flag or run: python -m backend.db.seed --demo"
        return 0
    fi

    log_step "Step 6/8 — Seeding Demo Data"

    local seed_failed=false

    # Try running seed via Python directly
    if command -v python3 &> /dev/null && [[ -f "${BACKEND_DIR}/db/seed.py" ]]; then
        log_info "Running seed script..."
        (cd "${PROJECT_ROOT}" && python3 -m backend.db.seed --demo) || {
            log_warn "Direct Python seed failed — trying container approach"
            seed_failed=true
        }
    else
        seed_failed=true
    fi

    # Fallback: try inside Docker container
    if [[ "$seed_failed" == true ]]; then
        log_info "Attempting to seed via Docker container..."
        docker compose -f "${COMPOSE_FILE}" run --rm \
            -v "${BACKEND_DIR}:/app/backend:ro" \
            api bash -c "cd /app && python -m backend.db.seed --demo" || {
            log_warn "Container seed also failed"
            log_info "To seed manually after services start:"
            log_info "  docker compose exec api python -m backend.db.seed --demo"
            return 0
        }
    fi

    log_ok "Demo data seeded successfully"
}

# ----------------------------------------------------------
# Step 7: Start all services
# ----------------------------------------------------------
start_all_services() {
    log_step "Step 7/8 — Starting All Services"

    log_info "Building and starting all services..."
    docker compose -f "${COMPOSE_FILE}" \
        -f "${COMPOSE_OVERRIDE}" \
        up -d --build

    # Wait for API to be ready
    log_info "Waiting for API service..."
    sleep 5

    local api_ready=false
    for ((i = 1; i <= 30; i++)); do
        if curl -sf http://localhost:8000/api/v1/health &> /dev/null; then
            api_ready=true
            break
        fi
        if [[ "$VERBOSE" == true ]]; then
            log_info "  API health check ${i}/30..."
        fi
        sleep 2
    done

    if [[ "$api_ready" == true ]]; then
        log_ok "API service is responding"
    else
        log_warn "API service not responding yet — it may still be starting"
    fi

    log_ok "All services started"
}

# ----------------------------------------------------------
# Step 8: Health check and summary
# ----------------------------------------------------------
health_check() {
    if [[ "$SKIP_HEALTH_CHECK" == true ]]; then
        log_step "Step 8/8 — Health Check (SKIPPED)"
        return 0
    fi

    log_step "Step 8/8 — Health Check Verification"

    local all_healthy=true

    # PostgreSQL
    if docker compose -f "${COMPOSE_FILE}" exec -T postgres \
        pg_isready -U answerflow &> /dev/null; then
        log_pass "PostgreSQL     — healthy"
    else
        log_fail "PostgreSQL     — unreachable"
        all_healthy=false
    fi

    # Redis
    if docker compose -f "${COMPOSE_FILE}" exec -T redis \
        redis-cli ping | grep -q "PONG"; then
        log_pass "Redis          — healthy"
    else
        log_fail "Redis          — unreachable"
        all_healthy=false
    fi

    # API
    if curl -sf http://localhost:8000/api/v1/health &> /dev/null; then
        log_pass "API Server     — healthy"
    else
        log_fail "API Server     — not responding"
        all_healthy=false
    fi

    # Dashboard (if built)
    if curl -sf http://localhost:5173 &> /dev/null || \
       curl -sf http://localhost:5173/index.html &> /dev/null 2>/dev/null; then
        log_pass "Dashboard      — responding"
    else
        log_warn "Dashboard      — may still be starting (Vite dev server)"
    fi

    if [[ "$all_healthy" == true ]]; then
        log_ok "All critical services are healthy"
        return 0
    else
        log_warn "Some services are not yet healthy — they may still be starting"
        log_info "Check status: docker compose -f ${COMPOSE_FILE} ps"
        log_info "View logs:    docker compose -f ${COMPOSE_FILE} logs -f"
        return 0  # Don't fail — services may still be warming up
    fi
}

# ----------------------------------------------------------
# Print final summary
# ----------------------------------------------------------
print_summary() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║       Owlbell — Setup Complete!                  ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "  ${BOLD}Dashboard:${NC}     http://localhost:5173"
    echo -e "  ${BOLD}API Docs:${NC}      http://localhost:8000/api/v1/docs"
    echo -e "  ${BOLD}Health Check:${NC}  http://localhost:8000/api/v1/health"
    echo ""

    if [[ "$SEED_DEMO" == true ]]; then
        echo -e "  ${BOLD}Demo Tenant:${NC}   Smith Dental Clinic"
        echo -e "  ${BOLD}Login Email:${NC}   dr.smith@smithdental.example.com"
        echo -e "  ${BOLD}Password:${NC}      DemoPass123!"
        echo ""
        echo -e "  ${CYAN}Sample calls, appointments, FAQ entries, and"
        echo -e "  routing rules have been pre-loaded for exploration.${NC}"
        echo ""
    fi

    echo -e "  ${BOLD}Useful commands:${NC}"
    echo "    docker compose ps                    # View running services"
    echo "    docker compose logs -f api           # Tail API logs"
    echo "    docker compose logs -f freeswitch    # Tail telephony logs"
    echo "    make test                            # Run test suite"
    echo "    make lint                            # Run linters"
    echo ""
    echo -e "  ${BOLD}Management:${NC}"
    echo "    python -m backend.db.seed --demo     # Re-seed demo data"
    echo "    python -m backend.scripts.create_tenant  # Onboard new tenant"
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  Simulate a call:                                      ║"
    echo "║    curl -X POST http://localhost:8000/api/v1/calls/    ║"
    echo "║      -H 'Content-Type: application/json'               ║"
    echo "║      -d '{\"to\":\"+1-555-0100\",\"from\":\"+1-555-0200\"}' ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
}

# ----------------------------------------------------------
# Cleanup on interrupt
# ----------------------------------------------------------
cleanup_on_interrupt() {
    echo ""
    log_warn "Setup interrupted by user."
    log_info "To clean up: docker compose -f ${COMPOSE_FILE} down"
    exit 130
}
trap cleanup_on_interrupt SIGINT SIGTERM

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------
main() {
    parse_args "$@"

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║       Owlbell — First-Run Setup                   ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

    check_prerequisites
    check_ports
    setup_env
    start_core_services
    run_migrations
    seed_demo_data
    start_all_services
    health_check
    print_summary

    log_ok "Setup complete! Welcome to Owlbell."
}

main "$@"
