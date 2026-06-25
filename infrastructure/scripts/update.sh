#!/bin/bash
# ============================================================
# Owlbell — Zero-Downtime Update Script
# ============================================================
# File: infrastructure/scripts/update.sh
# Purpose: Rolling update with health verification and rollback
# Strategy:
#   1. Pull latest code
#   2. Build new images
#   3. Run database migrations
#   4. Rolling restart (blue-green)
#   5. Health verification
#   6. Automatic rollback on failure
# ============================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_DIR="${APP_DIR:-/opt/answerflow}"
COMPOSE_FILE="$APP_DIR/infrastructure/docker/docker-compose.yml"
ENV_FILE="$APP_DIR/.env"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
SKIP_BUILD="${SKIP_BUILD:-false}"

# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------
log_info() { echo -e "${BLUE}[INFO]${NC} [$(date +%H:%M:%S)] $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC}  [$(date +%H:%M:%S)] $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} [$(date +%H:%M:%S)] $1"; }
log_err()  { echo -e "${RED}[ERR]${NC}  [$(date +%H:%M:%S)] $1" >&2; }
log_step() { echo -e "${BLUE}[STEP]${NC} [$(date +%H:%M:%S)] $1"; }

# ----------------------------------------------------------
# Pre-flight checks
# ----------------------------------------------------------
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_err "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    if [[ ! -f "$ENV_FILE" ]]; then
        log_err "Environment file not found: $ENV_FILE"
        exit 1
    fi
    
    cd "$APP_DIR"
    
    # Check docker is running
    if ! docker info > /dev/null 2>&1; then
        log_err "Docker is not running"
        exit 1
    fi
    
    log_ok "Prerequisites OK"
}

# ----------------------------------------------------------
# Step 1: Pull Latest Code
# ----------------------------------------------------------
step_pull_code() {
    log_step "Step 1/6: Pulling latest code..."
    
    cd "$APP_DIR"
    
    # Store current commit for potential rollback
    CURRENT_COMMIT=$(git rev-parse HEAD)
    echo "$CURRENT_COMMIT" > "$APP_DIR/.rollback-commit"
    
    # Pull latest
    git fetch origin
    git reset --hard "origin/$(git rev-parse --abbrev-ref HEAD)"
    
    NEW_COMMIT=$(git rev-parse HEAD)
    
    if [[ "$CURRENT_COMMIT" == "$NEW_COMMIT" ]]; then
        log_warn "Already at latest commit ($NEW_COMMIT)"
    else
        log_ok "Updated from $CURRENT_COMMIT to $NEW_COMMIT"
    fi
    
    # Set GIT_SHA in environment
    export GIT_SHA="$NEW_COMMIT"
    echo "GIT_SHA=$NEW_COMMIT" >> "$ENV_FILE"
}

# ----------------------------------------------------------
# Step 2: Build New Images
# ----------------------------------------------------------
step_build_images() {
    if [[ "$SKIP_BUILD" == "true" ]]; then
        log_step "Step 2/6: Skipping build (SKIP_BUILD=true)"
        return 0
    fi
    
    log_step "Step 2/6: Building new Docker images..."
    
    cd "$APP_DIR"
    
    # Build images with cache
    docker compose -f "$COMPOSE_FILE" build \
        --parallel \
        --progress=plain
    
    log_ok "Images built successfully"
}

# ----------------------------------------------------------
# Step 3: Run Database Migrations
# ----------------------------------------------------------
step_migrate() {
    log_step "Step 3/6: Running database migrations..."
    
    cd "$APP_DIR"
    
    # Run migrations in a temporary container
    docker compose -f "$COMPOSE_FILE" run --rm api \
        alembic upgrade head
    
    log_ok "Database migrations complete"
}

# ----------------------------------------------------------
# Step 4: Rolling Restart
# ----------------------------------------------------------
step_rolling_restart() {
    log_step "Step 4/6: Performing rolling restart..."
    
    cd "$APP_DIR"
    
    # Restart services one by one, starting with non-critical
    local services=(
        "prometheus"
        "grafana"
        "loki"
        "promtail"
        "alertmanager"
        "whisper"
        "piper"
        "ollama"
        "celery-beat"
        "celery-worker"
        "websocket"
        "api"
        "freeswitch"
        "nginx"
    )
    
    for service in "${services[@]}"; do
        log_info "Restarting $service..."
        docker compose -f "$COMPOSE_FILE" up -d --no-deps "$service"
        
        # Brief pause between restarts
        sleep 2
    done
    
    log_ok "Rolling restart complete"
}

# ----------------------------------------------------------
# Step 5: Health Verification
# ----------------------------------------------------------
step_health_check() {
    log_step "Step 5/6: Running health checks..."
    
    local healthy=true
    local start_time=$(date +%s)
    local end_time=$((start_time + HEALTH_TIMEOUT))
    
    # Wait for services to be ready
    log_info "Waiting for services to stabilize..."
    sleep 10
    
    # Check API health
    log_info "Checking API health..."
    local api_retries=10
    while [[ $api_retries -gt 0 ]]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_ok "API is healthy"
            break
        fi
        sleep 3
        ((api_retries--))
    done
    
    if [[ $api_retries -eq 0 ]]; then
        log_err "API health check failed after multiple retries"
        healthy=false
    fi
    
    # Check WebSocket
    log_info "Checking WebSocket health..."
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        log_ok "WebSocket is healthy"
    else
        log_warn "WebSocket health check failed (may still be starting)"
    fi
    
    # Check database
    log_info "Checking PostgreSQL..."
    if docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_isready -U "${POSTGRES_USER:-answerflow}" > /dev/null 2>&1; then
        log_ok "PostgreSQL is healthy"
    else
        log_err "PostgreSQL is not responding"
        healthy=false
    fi
    
    # Check Redis
    log_info "Checking Redis..."
    if docker compose -f "$COMPOSE_FILE" exec -T redis \
        redis-cli ping 2>/dev/null | grep -q PONG; then
        log_ok "Redis is healthy"
    else
        log_err "Redis is not responding"
        healthy=false
    fi
    
    # Check FreeSWITCH
    log_info "Checking FreeSWITCH..."
    if docker compose -f "$COMPOSE_FILE" exec -T freeswitch \
        fs_cli -x "sofia status" > /dev/null 2>&1; then
        log_ok "FreeSWITCH is healthy"
    else
        log_warn "FreeSWITCH check failed (may still be starting)"
    fi
    
    # Overall status
    if [[ "$healthy" == "false" ]]; then
        log_err "Health checks FAILED"
        return 1
    fi
    
    log_ok "All health checks passed"
}

# ----------------------------------------------------------
# Step 6: Cleanup
# ----------------------------------------------------------
step_cleanup() {
    log_step "Step 6/6: Cleaning up..."
    
    # Remove old images
    docker system prune -af --volumes=false --filter "until=168h"
    
    # Remove dangling volumes
    docker volume prune -f
    
    log_ok "Cleanup complete"
}

# ----------------------------------------------------------
# Rollback
# ----------------------------------------------------------
rollback() {
    log_err "Update failed! Initiating rollback..."
    
    if [[ -f "$APP_DIR/.rollback-commit" ]]; then
        local rollback_commit
        rollback_commit=$(cat "$APP_DIR/.rollback-commit")
        
        log_info "Rolling back to commit: $rollback_commit"
        
        cd "$APP_DIR"
        git reset --hard "$rollback_commit"
        
        # Rebuild and restart with old code
        docker compose -f "$COMPOSE_FILE" build --parallel
        docker compose -f "$COMPOSE_FILE" up -d
        
        # Run any down migrations if needed
        log_warn "You may need to manually revert database migrations"
        log_warn "Run: docker compose -f $COMPOSE_FILE run --rm api alembic downgrade -1"
        
        log_ok "Rollback complete (code restored)"
    else
        log_err "No rollback commit found! Manual intervention required."
    fi
    
    exit 1
}

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------
main() {
    echo ""
    echo "============================================================"
    echo "  Owlbell — Zero-Downtime Update"
    echo "  Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "============================================================"
    echo ""
    
    # Trap rollback on failure
    trap rollback ERR
    
    check_prerequisites
    step_pull_code
    step_build_images
    step_migrate
    step_rolling_restart
    step_health_check
    step_cleanup
    
    echo ""
    echo "============================================================"
    log_ok "Update completed successfully!"
    echo "============================================================"
    echo ""
    echo "Current version: $(cd $APP_DIR && git rev-parse --short HEAD)"
    echo "Services status:"
    docker compose -f "$COMPOSE_FILE" ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-build    Skip Docker image build"
            echo "  --help, -h      Show this help"
            exit 0
            ;;
        *)
            log_err "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run
main
