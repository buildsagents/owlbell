#!/bin/bash
# ============================================================
# Owlbell — One-Command Server Setup
# ============================================================
# File: infrastructure/scripts/setup.sh
# Purpose: Automates full server provisioning for Oracle Cloud
#           Always Free ARM64 instance (Ubuntu 22.04)
# Steps:
#   1. Update system
#   2. Install Docker + Docker Compose
#   3. Install certbot (Let's Encrypt)
#   4. Clone repository
#   5. Generate secrets
#   6. Start services
#   7. Run migrations
#   8. Create admin user
# Prerequisites: Ubuntu 22.04 ARM64, SSH access
# ============================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/answerflow"
REPO_URL="https://github.com/answerflowai/answerflow.git"
DOMAIN="${DOMAIN:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"

# ----------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC}  $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERR]${NC}  $1" >&2; }

# Generate a secure random secret
generate_secret() {
    openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "Running as root. It is recommended to use a non-root user with sudo."
    fi
}

# ----------------------------------------------------------
# Step 1: System Update
# ----------------------------------------------------------
step_system_update() {
    log_info "Step 1/8: Updating system packages..."
    
    export DEBIAN_FRONTEND=noninteractive
    
    sudo apt-get update -qq
    sudo apt-get upgrade -y -qq
    sudo apt-get install -y -qq \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common \
        python3-pip \
        python3-venv \
        git \
        vim \
        nano \
        htop \
        iotop \
        ncdu \
        tree \
        jq \
        unzip \
        ufw \
        fail2ban \
        openssl \
        cron \
        logrotate \
        rclone
    
    log_ok "System packages updated"
}

# ----------------------------------------------------------
# Step 2: Install Docker & Docker Compose
# ----------------------------------------------------------
step_install_docker() {
    log_info "Step 2/8: Installing Docker and Docker Compose..."
    
    # Remove old versions
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Add Docker GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    local arch=$(dpkg --print-architecture)
    echo "deb [arch=$arch signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker "$USER" || true
    
    # Start Docker
    sudo systemctl enable docker
    sudo systemctl start docker
    
    # Verify
    docker --version
    docker compose version
    
    log_ok "Docker installed ($(docker --version))"
}

# ----------------------------------------------------------
# Step 3: Install certbot
# ----------------------------------------------------------
step_install_certbot() {
    log_info "Step 3/8: Installing certbot for SSL..."
    
    sudo apt-get install -y -qq certbot
    
    # Create webroot for ACME challenges
    sudo mkdir -p /var/www/certbot
    
    log_ok "Certbot installed"
}

# ----------------------------------------------------------
# Step 4: Clone Repository
# ----------------------------------------------------------
step_clone_repo() {
    log_info "Step 4/8: Cloning repository..."
    
    if [[ -d "$APP_DIR" ]]; then
        log_warn "$APP_DIR already exists. Updating..."
        cd "$APP_DIR"
        git fetch origin
        git reset --hard origin/main
    else
        sudo mkdir -p "$(dirname $APP_DIR)"
        sudo git clone "$REPO_URL" "$APP_DIR"
        sudo chown -R "$USER:$USER" "$APP_DIR"
    fi
    
    cd "$APP_DIR"
    log_ok "Repository cloned to $APP_DIR"
}

# ----------------------------------------------------------
# Step 5: Generate Secrets & Configure Environment
# ----------------------------------------------------------
step_configure_env() {
    log_info "Step 5/8: Generating secrets and configuring environment..."
    
    cd "$APP_DIR"
    
    # Prompt for required values if not set
    if [[ -z "$DOMAIN" ]]; then
        read -p "Enter your domain (e.g., owlbell.xyz): " DOMAIN
    fi
    
    if [[ -z "$ADMIN_EMAIL" ]]; then
        read -p "Enter admin email for SSL/letsencrypt: " ADMIN_EMAIL
    fi
    
    # Generate secrets
    local postgres_password=$(generate_secret)
    local app_secret=$(generate_secret)
    local jwt_secret=$(generate_secret)
    local minio_access=$(openssl rand -hex 16)
    local minio_secret=$(openssl rand -hex 32)
    local freeswitch_password=$(openssl rand -hex 16)
    local grafana_password=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
    
    # Write .env file
    cat > "$APP_DIR/.env" <<EOF
# ============================================================
# Owlbell — Production Environment Variables
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
# ============================================================

# -----------------------------------------------------------
# Domain & SSL
# -----------------------------------------------------------
DOMAIN=$DOMAIN
ADMIN_EMAIL=$ADMIN_EMAIL

# -----------------------------------------------------------
# Database (PostgreSQL)
# -----------------------------------------------------------
POSTGRES_USER=answerflow
POSTGRES_PASSWORD=$postgres_password
POSTGRES_DB=answerflow

# -----------------------------------------------------------
# Application Secrets
# -----------------------------------------------------------
APP_SECRET_KEY=$app_secret
JWT_SECRET_KEY=$jwt_secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# -----------------------------------------------------------
# MinIO (S3-compatible object storage)
# -----------------------------------------------------------
MINIO_ACCESS_KEY=$minio_access
MINIO_SECRET_KEY=$minio_secret
MINIO_BUCKET_NAME=answerflow
MINIO_USE_SSL=false

# -----------------------------------------------------------
# FreeSWITCH
# -----------------------------------------------------------
FREESWITCH_ESL_PASSWORD=$freeswitch_password

# -----------------------------------------------------------
# Grafana
# -----------------------------------------------------------
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=$grafana_password

# -----------------------------------------------------------
# AI Services
# -----------------------------------------------------------
OLLAMA_MODEL=phi3:mini
WHISPER_MODEL=ggml-base.en.bin
PIPER_VOICE=en_US-lessac-medium

# -----------------------------------------------------------
# Backup (optional — configure for your storage)
# -----------------------------------------------------------
# BACKUP_S3_BUCKET=
# BACKUP_ACCESS_KEY=
# BACKUP_SECRET_KEY=
# BACKUP_S3_ENDPOINT=
# BACKUP_NOTIFICATION_URL=

# -----------------------------------------------------------
# Deployment
# -----------------------------------------------------------
GIT_SHA=latest
APP_ENV=production
LOG_LEVEL=INFO
EOF
    
    # Secure the .env file
    chmod 600 "$APP_DIR/.env"
    
    log_ok "Environment configured"
    log_info "Grafana admin password: $grafana_password"
    log_info "Saved to: $APP_DIR/.env (chmod 600)"
    
    # Save credentials file for admin reference
    cat > "$APP_DIR/.credentials" <<EOF
# Owlbell — Admin Credentials
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
# KEEP THIS FILE SECURE — chmod 600

Domain:         $DOMAIN
Admin Email:    $ADMIN_EMAIL
Grafana User:   admin
Grafana Pass:   $grafana_password
DB User:        answerflow
DB Pass:        $postgres_password
MinIO Access:   $minio_access
MinIO Secret:   $minio_secret
EOF
    chmod 600 "$APP_DIR/.credentials"
    
    log_info "Credentials saved to: $APP_DIR/.credentials (chmod 600)"
}

# ----------------------------------------------------------
# Step 6: Obtain SSL Certificates
# ----------------------------------------------------------
step_obtain_ssl() {
    log_info "Step 6/8: Obtaining SSL certificates..."
    
    # Stop any service on port 80
    sudo systemctl stop nginx 2>/dev/null || true
    
    # Obtain certificate
    sudo certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$ADMIN_EMAIL" \
        -d "$DOMAIN" \
        -d "app.$DOMAIN" \
        -d "api.$DOMAIN" \
        -d "monitoring.$DOMAIN" \
        -d "storage.$DOMAIN" \
        --deploy-hook "docker exec af_nginx nginx -s reload 2>/dev/null || true"
    
    # Setup auto-renewal
    sudo systemctl enable certbot.timer 2>/dev/null || true
    
    # Add cron job for cert renewal if systemd timer not available
    (sudo crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'docker exec af_nginx nginx -s reload 2>/dev/null || true'") | sudo crontab -
    
    log_ok "SSL certificates obtained for $DOMAIN"
}

# ----------------------------------------------------------
# Step 7: Start Services
# ----------------------------------------------------------
step_start_services() {
    log_info "Step 7/8: Starting services..."
    
    cd "$APP_DIR"
    
    # Create necessary directories
    mkdir -p "$APP_DIR/data/postgres"
    mkdir -p "$APP_DIR/data/redis"
    mkdir -p "$APP_DIR/data/minio"
    mkdir -p "$APP_DIR/data/grafana"
    mkdir -p "$APP_DIR/data/prometheus"
    mkdir -p "$APP_DIR/data/loki"
    mkdir -p "$APP_DIR/data/whisper_models"
    mkdir -p "$APP_DIR/data/ollama_models"
    mkdir -p "$APP_DIR/data/recordings"
    
    # Pull images
    log_info "Pulling Docker images..."
    docker compose -f infrastructure/docker/docker-compose.yml pull
    
    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker compose -f infrastructure/docker/docker-compose.yml up -d \
        postgres redis minio loki promtail
    
    # Wait for database to be ready
    log_info "Waiting for PostgreSQL..."
    for i in {1..30}; do
        if docker compose -f infrastructure/docker/docker-compose.yml exec -T postgres \
            pg_isready -U answerflow > /dev/null 2>&1; then
            log_ok "PostgreSQL is ready"
            break
        fi
        sleep 2
    done
    
    # Wait for Redis
    log_info "Waiting for Redis..."
    for i in {1..30}; do
        if docker compose -f infrastructure/docker/docker-compose.yml exec -T redis \
            redis-cli ping 2>/dev/null | grep -q PONG; then
            log_ok "Redis is ready"
            break
        fi
        sleep 2
    done
    
    # Wait for MinIO
    log_info "Waiting for MinIO..."
    for i in {1..30}; do
        if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
            log_ok "MinIO is ready"
            break
        fi
        sleep 2
    done
    
    # Start all remaining services
    log_info "Starting all services..."
    docker compose -f infrastructure/docker/docker-compose.yml up -d
    
    log_ok "All services started"
}

# ----------------------------------------------------------
# Step 8: Run Migrations & Create Admin User
# ----------------------------------------------------------
step_finalize() {
    log_info "Step 8/8: Running migrations and creating admin user..."
    
    cd "$APP_DIR"
    
    # Run database migrations
    log_info "Running database migrations..."
    docker compose -f infrastructure/docker/docker-compose.yml run --rm api \
        alembic upgrade head
    
    log_ok "Database migrations complete"
    
    # Create initial admin user (interactive)
    log_info "Creating admin user..."
    echo ""
    echo "=== Create Admin User ==="
    docker compose -f infrastructure/docker/docker-compose.yml run --rm api \
        python -m app.cli create-admin 2>/dev/null || \
    log_warn "Admin creation skipped (CLI not available yet — create via dashboard)"
    
    log_ok "Setup complete!"
    echo ""
    echo "============================================================"
    echo -e "${GREEN}Owlbell is now running!${NC}"
    echo "============================================================"
    echo ""
    echo "URLs:"
    echo "  Dashboard:  https://app.$DOMAIN"
    echo "  API:        https://api.$DOMAIN/api/v1"
    echo "  Grafana:    https://monitoring.$DOMAIN"
    echo "  MinIO:      https://storage.$DOMAIN"
    echo ""
    echo "Credentials saved in: $APP_DIR/.credentials"
    echo "  cat $APP_DIR/.credentials"
    echo ""
    echo "Useful commands:"
    echo "  cd $APP_DIR"
    echo "  docker compose -f infrastructure/docker/docker-compose.yml ps"
    echo "  docker compose -f infrastructure/docker/docker-compose.yml logs -f api"
    echo "  docker compose -f infrastructure/docker/docker-compose.yml logs -f freeswitch"
    echo ""
    echo "============================================================"
}

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------
main() {
    echo ""
    echo "============================================================"
    echo "  Owlbell — Server Setup"
    echo "  Target: Oracle Cloud Always Free (ARM64)"
    echo "============================================================"
    echo ""
    
    # Check prerequisites
    check_root
    
    if [[ -z "${DOMAIN:-}" ]]; then
        echo "Please set the DOMAIN environment variable:"
        echo "  export DOMAIN=yourdomain.com"
        echo "  export ADMIN_EMAIL=you@example.com"
        echo "  ./setup.sh"
        exit 1
    fi
    
    # Run all steps
    step_system_update
    step_install_docker
    step_install_certbot
    step_clone_repo
    step_configure_env
    step_obtain_ssl
    step_start_services
    step_finalize
    
    log_ok "Setup complete! Enjoy Owlbell."
}

# Run main function
main "$@"
