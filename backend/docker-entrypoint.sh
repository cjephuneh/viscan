#!/bin/sh
# Apply pending Alembic migrations, then start the API.
# Set RUN_MIGRATIONS=false to skip (e.g. when several replicas share one DB
# and migrations are applied by a separate job).
set -e

export FLASK_APP="${FLASK_APP:-run.py}"

if [ "${RUN_MIGRATIONS:-true}" != "false" ]; then
    echo "[entrypoint] Applying database migrations..."
    attempt=1
    until flask db upgrade; do
        if [ "$attempt" -ge 10 ]; then
            echo "[entrypoint] Migrations failed after $attempt attempts; aborting." >&2
            exit 1
        fi
        echo "[entrypoint] Database not ready (attempt $attempt); retrying in 3s..."
        attempt=$((attempt + 1))
        sleep 3
    done
    echo "[entrypoint] Migrations up to date."
fi

exec "$@"
