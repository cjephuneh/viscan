#!/usr/bin/env bash
# ==============================================================================
# Restore a ViScan Postgres dump created by scripts/backup-db.sh.
#
# Usage (on the server):
#   ./scripts/restore-db.sh viscan /home/ubuntu/.viscan-backups/viscan_YYYYMMDD_HHMMSS.sql.gz
#   ./scripts/restore-db.sh app_db  /home/ubuntu/.viscan-backups/app_db_YYYYMMDD_HHMMSS.sql.gz
#
# WARNING: this replaces the current contents of the target database.
# ==============================================================================
set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-postgres-db}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/ubuntu/.viscan-backups}"

usage() {
    echo "Usage: $0 <viscan|app_db> <path-to-.sql.gz>" >&2
    echo "Available backups in ${BACKUP_ROOT}:" >&2
    ls -lh "${BACKUP_ROOT}"/*.sql.gz 2>/dev/null || echo "  (none)" >&2
    exit 2
}

[ "${1:-}" = "" ] || [ "${2:-}" = "" ] && usage
DB_NAME="$1"
FILE="$2"

case "$DB_NAME" in
    viscan|app_db) ;;
    *) echo "unknown database: $DB_NAME (use viscan or app_db)" >&2; exit 2 ;;
esac

if [ ! -f "$FILE" ]; then
    echo "Error: file not found: $FILE" >&2
    exit 1
fi

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    echo "Error: docker container '$CONTAINER' not found" >&2
    exit 1
fi

echo "=================================================================="
echo "  Restore ${FILE}"
echo "  into database '${DB_NAME}' on container '${CONTAINER}'"
echo "  This REPLACES current data in '${DB_NAME}'."
echo "=================================================================="
read -r -p "Type the database name (${DB_NAME}) to confirm: " confirm
[ "$confirm" = "$DB_NAME" ] || { echo "Aborted."; exit 1; }

# Recreate a clean database so --clean dumps apply cleanly.
docker exec "$CONTAINER" psql -U postgres -v ON_ERROR_STOP=1 -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
    >/dev/null || true
docker exec "$CONTAINER" psql -U postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker exec "$CONTAINER" psql -U postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER dev_user;"

if [[ "$FILE" == *.gz ]]; then
    gunzip -c "$FILE" | docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -v ON_ERROR_STOP=1
else
    cat "$FILE" | docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -v ON_ERROR_STOP=1
fi

echo "✔ Restored ${DB_NAME} from ${FILE}"
echo "  Restart tip: docker compose -f /home/ubuntu/viscan/docker-compose.prod.yml restart ai-interpreter ai-avatar backend"
