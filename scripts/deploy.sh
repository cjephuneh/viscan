#!/usr/bin/env bash
# ==============================================================================
# ViScan manual deployment from a developer machine.
#
# Normal deployments are automatic: push to main -> GitHub Actions runs the
# tests -> the server's timer (scripts/server-deploy.sh) deploys the commit.
# Use this script when you need to push env files to the server or force a
# deploy right now without waiting for the timer.
#
# Usage:
#   ./scripts/deploy.sh                 run all test suites, sync env files, deploy
#   ./scripts/deploy.sh --skip-tests    skip the local test suites
#   ./scripts/deploy.sh --env-only      only copy .env files to the server
#   SERVER=gp5 ./scripts/deploy.sh      SSH host alias (default gp5)
# ==============================================================================
set -euo pipefail

SERVER="${SERVER:-gp5}"
REMOTE_DIR="/home/ubuntu/viscan"
SKIP_TESTS=false
ENV_ONLY=false
cd "$(dirname "$0")/.."

for arg in "$@"; do
    case "$arg" in
        --skip-tests) SKIP_TESTS=true ;;
        --env-only) ENV_ONLY=true ;;
        --server=*) SERVER="${arg#*=}" ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

echo "=================================================================="
echo "    ViScan manual deploy -> ${SERVER}:${REMOTE_DIR}"
echo "=================================================================="

# ------------------------------------------------------------------------------
# Phase 1: local test suites (same commands as .github/workflows/ci.yml)
# ------------------------------------------------------------------------------
if [ "$SKIP_TESTS" = false ] && [ "$ENV_ONLY" = false ]; then
    echo; echo "▶ [1/3] Running test suites..."
    py() { # py <service-dir> -> python interpreter to use
        if [ -x "$1/.venv/bin/python" ]; then echo "$1/.venv/bin/python"; else echo python3; fi
    }
    (cd backend        && FLASK_CONFIG=testing "$(py .)" -m pytest -q)
    (cd ai-interpreter && INTERPRETER_MODE=heuristic "$(py .)" -m pytest -q)
    (cd ai-avatar      && ENVIRONMENT=testing "$(py .)" -m pytest -q)
    (cd frontend       && npm test --silent)
    echo "✔ All test suites passed."
fi

# ------------------------------------------------------------------------------
# Phase 2: env files (never committed; copied only if present locally)
# ------------------------------------------------------------------------------
echo; echo "▶ [2/3] Syncing environment files to ${SERVER}..."
ssh -o BatchMode=yes -o ConnectTimeout=10 "$SERVER" "mkdir -p $REMOTE_DIR/ai-interpreter $REMOTE_DIR/ai-avatar $REMOTE_DIR/backend"
for f in .env ai-interpreter/.env ai-avatar/.env backend/.env; do
    if [ -f "$f" ]; then
        scp -q "$f" "${SERVER}:${REMOTE_DIR}/$f" && echo "  ✔ $f"
    else
        echo "  - $f not present locally; keeping the server's copy"
    fi
done
[ "$ENV_ONLY" = true ] && { echo "Done (env only)."; exit 0; }

# ------------------------------------------------------------------------------
# Phase 3: deploy through the server-side deployer (same code path as the timer)
# ------------------------------------------------------------------------------
echo; echo "▶ [3/3] Deploying on ${SERVER}..."
if ! git diff --quiet HEAD -- . ':!*.env*' 2>/dev/null; then
    echo "  ⚠ You have uncommitted changes; the server deploys origin/main, not your working tree."
fi
ssh "$SERVER" "$REMOTE_DIR/scripts/server-deploy.sh --force --skip-ci-check"

echo
echo "=================================================================="
echo "    ✔ Deployed. Gateway: http://16.192.134.200/"
echo "    Logs: ssh ${SERVER} tail -f /home/ubuntu/.viscan-deploy/deploy.log"
echo "=================================================================="
