#!/bin/bash
# ============================================================
# Owlbell — Automated Backup Script
# ============================================================
# File: infrastructure/scripts/backup.sh
# Purpose: Backup PostgreSQL, Redis, MinIO data
# Strategy:
#   - pg_dump PostgreSQL (compressed)
#   - Redis SAVE + copy RDB
#   - MinIO bucket sync
#   - Compress and encrypt with GPG
#   - Upload to remote storage (rclone)
#   - Retention: keep 30 daily backups
# Schedule: Run via cron at 3 AM daily
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
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_NAME="answerflow_backup_${TIMESTAMP}"
BACKUP_TMP="/tmp/${BACKUP_NAME}"

# GPG encryption key (optional)
GPG_KEY="${GPG_KEY:-}"

# Remote storage config for rclone (optional)
RCLONE_REMOTE="${RCLONE_REMOTE:-}"  # e.g., "mega:answerflow-backups"

# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------
log_info() { echo -e "${BLUE}[INFO]${NC} [$(date +%H:%M:%S)] $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC}  [$(date +%H:%M:%S)] $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} [$(date +%H:%M:%S)] $1"; }
log_err()  { echo -e "${RED}[ERR]${NC}  [$(date +%H:%M:%S)] $1" >&2; }

# ----------------------------------------------------------
# Pre-flight checks
# ----------------------------------------------------------
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check docker
    if ! command -v docker &> /dev/null; then
        log_err "Docker not found. Is Docker installed?"
        exit 1
    fi
    
    # Check docker compose
    if ! docker compose version &> /dev/null; then
        log_err "Docker Compose plugin not found."
        exit 1
    fi
    
    # Create backup directories
    mkdir -p "$BACKUP_DIR/daily"
    mkdir -p "$BACKUP_DIR/weekly"
    mkdir -p "$BACKUP_TMP"
    
    log_ok "Prerequisites OK"
}

# ----------------------------------------------------------
# Backup PostgreSQL
# ----------------------------------------------------------
backup_postgres() {
    log_info "Backing up PostgreSQL..."
    
    local output_file="${BACKUP_TMP}/postgres.sql.gz"
    
    # Get DB credentials from environment
    local db_user="${POSTGRES_USER:-answerflow}"
    local db_name="${POSTGRES_DB:-answerflow}"
    
    # Run pg_dump inside the postgres container
    docker exec af_postgres pg_dump \
        -U "$db_user" \
        -d "$db_name" \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists \
        --verbose 2>/dev/null | gzip > "$output_file"
    
    local size=$(du -h "$output_file" | cut -f1)
    log_ok "PostgreSQL backed up ($size)"
}

# ----------------------------------------------------------
# Backup Redis
# ----------------------------------------------------------
backup_redis() {
    log_info "Backing up Redis..."
    
    local output_file="${BACKUP_TMP}/redis.rdb.gz"
    
    # Trigger BGSAVE and wait
    docker exec af_redis redis-cli BGSAVE > /dev/null 2>&1
    
    # Wait for save to complete (check LASTSAVE)
    local initial_save=$(docker exec af_redis redis-cli LASTSAVE)
    local retries=30
    
    while [[ $retries -gt 0 ]]; do
        sleep 1
        local current_save=$(docker exec af_redis redis-cli LASTSAVE)
        if [[ "$current_save" != "$initial_save" ]]; then
            break
        fi
        ((retries--))
    done
    
    # Copy the RDB file
    docker cp "af_redis:/data/dump.rdb" - 2>/dev/null | gzip > "$output_file"
    
    local size=$(du -h "$output_file" | cut -f1)
    log_ok "Redis backed up ($size)"
}

# ----------------------------------------------------------
# Backup MinIO
# ----------------------------------------------------------
backup_minio() {
    log_info "Backing up MinIO..."
    
    local output_dir="${BACKUP_TMP}/minio"
    mkdir -p "$output_dir"
    
    # Get MinIO credentials
    local access_key="${MINIO_ACCESS_KEY:-}"
    local secret_key="${MINIO_SECRET_KEY:-}"
    
    if [[ -z "$access_key" || -z "$secret_key" ]]; then
        log_warn "MinIO credentials not set, reading from .env"
        if [[ -f "$APP_DIR/.env" ]]; then
            access_key=$(grep '^MINIO_ACCESS_KEY=' "$APP_DIR/.env" | cut -d= -f2)
            secret_key=$(grep '^MINIO_SECRET_KEY=' "$APP_DIR/.env" | cut -d= -f2)
        fi
    fi
    
    # Use mc client or curl to backup buckets
    if docker exec af_minio mc --version > /dev/null 2>&1; then
        docker exec af_minio mc mirror \
            /data/"${MINIO_BUCKET_NAME:-answerflow}" \
            /tmp/minio-backup 2>/dev/null || true
        docker cp "af_minio:/tmp/minio-backup" "$output_dir/" 2>/dev/null || true
    else
        # Fallback: copy data volume directly
        log_warn "mc not available, copying data volume"
        docker run --rm \
            -v af_minio_data:/data:ro \
            -v "$output_dir:/backup" \
            alpine:latest \
            sh -c 'cp -r /data/* /backup/ 2>/dev/null || true' || true
    fi
    
    # Compress
    tar -czf "${output_dir}.tar.gz" -C "$output_dir" . 2>/dev/null || true
    rm -rf "$output_dir"
    
    local size=$(du -h "${output_dir}.tar.gz" 2>/dev/null | cut -f1 || echo "0")
    log_ok "MinIO backed up ($size)"
}

# ----------------------------------------------------------
# Compress & Encrypt
# ----------------------------------------------------------
compress_and_encrypt() {
    log_info "Compressing backup archive..."
    
    local archive="${BACKUP_DIR}/daily/${BACKUP_NAME}.tar.gz"
    
    # Create tar.gz archive
    tar -czf "$archive" -C "/tmp" "$BACKUP_NAME"
    
    local size=$(du -h "$archive" | cut -f1)
    log_ok "Archive created: $archive ($size)"
    
    # Encrypt with GPG if key is available
    if [[ -n "$GPG_KEY" ]] && command -v gpg &> /dev/null; then
        log_info "Encrypting with GPG..."
        gpg --batch --yes --recipient "$GPG_KEY" --encrypt --trust-model always "$archive"
        rm -f "$archive"
        archive="${archive}.gpg"
        local enc_size=$(du -h "$archive" | cut -f1)
        log_ok "Encrypted archive: $archive ($enc_size)"
    fi
    
    echo "$archive"
}

# ----------------------------------------------------------
# Upload to Remote Storage
# ----------------------------------------------------------
upload_remote() {
    local archive="$1"
    
    if [[ -z "$RCLONE_REMOTE" ]]; then
        log_warn "No RCLONE_REMOTE configured. Skipping remote upload."
        log_info "To configure remote backup:"
        log_info "  1. Install rclone: https://rclone.org/install/"
        log_info "  2. Configure remote: rclone config"
        log_info "  3. Set RCLONE_REMOTE env var"
        return 0
    fi
    
    log_info "Uploading to remote storage ($RCLONE_REMOTE)..."
    
    if ! command -v rclone &> /dev/null; then
        log_warn "rclone not installed. Skipping remote upload."
        return 0
    fi
    
    # Upload with progress
    rclone copy "$archive" "$RCLONE_REMOTE/daily/" \
        --progress \
        --transfers 4 \
        --checkers 8 \
        --retries 3 \
        --low-level-retries 10 \
        2>&1 | tail -5
    
    log_ok "Uploaded to remote storage"
}

# ----------------------------------------------------------
# Retention Policy
# ----------------------------------------------------------
apply_retention() {
    log_info "Applying retention policy (${BACKUP_RETENTION_DAYS} days)..."
    
    # Remove old daily backups
    local removed=$(find "$BACKUP_DIR/daily" -name "answerflow_backup_*.tar.gz*" \
        -mtime +$BACKUP_RETENTION_DAYS -print -delete 2>/dev/null | wc -l)
    
    log_ok "Removed $removed old backup(s)"
    
    # Keep weekly backups (every 7th day)
    local day_of_week=$(date +%u)
    if [[ "$day_of_week" == "7" ]]; then
        log_info "Sunday — creating weekly backup copy..."
        local latest=$(ls -t "$BACKUP_DIR/daily"/*.tar.gz* 2>/dev/null | head -1)
        if [[ -n "$latest" ]]; then
            cp "$latest" "$BACKUP_DIR/weekly/"
            log_ok "Weekly backup saved"
        fi
    fi
    
    # Clean old weekly backups (keep 12 weeks)
    local removed_weekly=$(find "$BACKUP_DIR/weekly" -name "answerflow_backup_*.tar.gz*" \
        -mtime +84 -print -delete 2>/dev/null | wc -l)
    
    if [[ "$removed_weekly" -gt 0 ]]; then
        log_ok "Removed $removed_weekly old weekly backup(s)"
    fi
    
    # Disk usage summary
    local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log_info "Total backup storage: $total_size"
}

# ----------------------------------------------------------
# Cleanup
# ----------------------------------------------------------
cleanup() {
    rm -rf "$BACKUP_TMP"
    log_info "Temporary files cleaned up"
}

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------
main() {
    echo ""
    echo "============================================================"
    echo "  Owlbell — Backup"
    echo "  Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "============================================================"
    echo ""
    
    # Trap cleanup on exit
    trap cleanup EXIT
    
    check_prerequisites
    backup_postgres
    backup_redis
    backup_minio
    
    local archive
    archive=$(compress_and_encrypt)
    upload_remote "$archive"
    apply_retention
    
    echo ""
    echo "============================================================"
    log_ok "Backup complete: $(basename "$archive")"
    echo "============================================================"
}

# Run
main "$@"
