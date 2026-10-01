#!/usr/bin/env bash
# ==============================================================================
# Daily Postgres dump for ViScan on the production host (gp5).
#
# Dumps:
#   - viscan  -> clinician screening / AI interpreter / intake history
#   - app_db  -> ai-avatar video reports (and any other app_db data)
#
# Usage (on the server):
#   ./scripts/backup-db.sh
#   KEEP_DAYS=30 ./scripts/backup-db.sh
#
# Restores: ./scripts/restore-db.sh <db_name> <path-to-.sql.gz>
# ==============================================================================
set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-postgres-db}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/ubuntu/.viscan-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_DIR="/home/ubuntu/.viscan-deploy"
LOG_FILE="${LOG_DIR}/backup.log"
DBS=(viscan app_db)

mkdir -p "$BACKUP_ROOT" "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    log "ERROR: docker container '$CONTAINER' not found"
    exit 1
fi
if ! docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
    log "ERROR: postgres in '$CONTAINER' is not ready"
    exit 1
fi

log "starting backup stamp=$STAMP keep_days=$KEEP_DAYS"
for db in "${DBS[@]}"; do
    out="${BACKUP_ROOT}/${db}_${STAMP}.sql.gz"
    # Prefer the DB owner when present; fall back to the superuser.
    if docker exec "$CONTAINER" psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1; then
        docker exec "$CONTAINER" pg_dump -U postgres --clean --if-exists --no-owner --no-acl "$db" \
            | gzip -c >"$out"
        size="$(du -h "$out" | awk '{print $1}')"
        log "ok  $db -> $out ($size)"
    else
        log "skip $db (database does not exist)"
    fi
done

# Drop dumps older than KEEP_DAYS.
deleted="$(find "$BACKUP_ROOT" -type f -name '*.sql.gz' -mtime "+${KEEP_DAYS}" -print -delete | wc -l | tr -d ' ')"
log "retention: removed ${deleted} file(s) older than ${KEEP_DAYS} days"
log "done. latest:"
ls -lh "$BACKUP_ROOT"/*.sql.gz 2>/dev/null | tail -n 6 || true
