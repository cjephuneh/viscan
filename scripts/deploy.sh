#!/bin/bash
# ==============================================================================
# ViScan CI/CD Automation & Deployment Script
# 
# Usage:
#   ./scripts/deploy.sh [--skip-tests] [--server gp5]
# ==============================================================================
set -e

SERVER="${SERVER:-gp5}"
REMOTE_DIR="/home/ubuntu/viscan"
SKIP_TESTS=false

for arg in "$@"; do
    case $arg in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --server=*)
            SERVER="${arg#*=}"
            shift
            ;;
    esac
done

echo "=================================================================="
echo "    ViScan Production Deployment Pipeline                         "
echo "    Target Server: ${SERVER}                                      "
echo "=================================================================="

# ------------------------------------------------------------------------------
# Phase 1: Automated Test Verification Gate
# ------------------------------------------------------------------------------
if [ "$SKIP_TESTS" = false ]; then
    echo ""
    echo "▶ [Phase 1/3] Running Automated Test Suites..."
    
    # 1. AI Avatar Tests
    echo "  → Testing ai-avatar service..."
    if [ -f "ai-avatar/.venv/bin/pytest" ]; then
        ai-avatar/.venv/bin/pytest ai-avatar/tests/ -q
    else
        docker compose -f ai-avatar/docker-compose.yml run --rm test
    fi
    echo "  ✔ ai-avatar test suite passed!"

    echo "✔ All automated pre-deployment tests PASSED!"
else
    echo "⚠ [Phase 1/3] Pre-deployment tests skipped (--skip-tests)."
fi

# ------------------------------------------------------------------------------
# Phase 2: Remote Codebase Synchronization via SSH
# ------------------------------------------------------------------------------
echo ""
echo "▶ [Phase 2/3] Synchronizing Codebase to Remote Server (${SERVER})..."

# Verify SSH connectivity
echo "  → Checking SSH connection to ${SERVER}..."
ssh -o BatchMode=yes -o ConnectTimeout=10 "${SERVER}" "echo '  ✔ SSH connection established.'"

# Ensure target directory exists and repository is cloned/updated
ssh "${SERVER}" bash -s << 'EOF'
set -e
TARGET="/home/ubuntu/viscan"

if [ ! -d "$TARGET/.git" ]; then
    echo "  → Cloning repository into $TARGET..."
    git clone https://github.com/cjephuneh/viscan.git "$TARGET"
fi

cd "$TARGET"
echo "  → Pulling latest changes on main branch..."
git fetch origin main
git checkout main
git reset --hard origin/main

echo "  ✔ Remote code synchronized to commit $(git rev-parse --short HEAD)."
EOF

# Sync environment configuration files securely to remote
echo "  → Ensuring environment configuration files on ${SERVER}..."
if [ -f "ai-avatar/.env" ]; then
    scp -q "ai-avatar/.env" "${SERVER}:${REMOTE_DIR}/ai-avatar/.env"
fi
if [ -f "ai-interpreter/.env.example" ]; then
    ssh "${SERVER}" "test -f ${REMOTE_DIR}/ai-interpreter/.env || cp ${REMOTE_DIR}/ai-interpreter/.env.example ${REMOTE_DIR}/ai-interpreter/.env"
fi
if [ -f "backend/.env.example" ]; then
    ssh "${SERVER}" "test -f ${REMOTE_DIR}/backend/.env || cp ${REMOTE_DIR}/backend/.env.example ${REMOTE_DIR}/backend/.env"
fi

# ------------------------------------------------------------------------------
# Phase 3: Build & Launch Production Containers
# ------------------------------------------------------------------------------
echo ""
echo "▶ [Phase 3/3] Building and Launching Production Services on ${SERVER}..."

ssh "${SERVER}" bash -s << 'EOF'
set -e
cd /home/ubuntu/viscan

echo "  → Building and starting containers via docker-compose.prod.yml..."
docker compose -f docker-compose.prod.yml up --build -d

echo "  → Waiting for services to stabilize..."
sleep 5

echo "  → Running health checks..."
# Check Nginx Gateway
if curl -sf http://localhost/health > /dev/null; then
    echo "  ✔ Nginx Gateway is HEALTHY (port 80)"
else
    echo "  ⚠ Warning: Gateway returned non-200"
fi

# Check Docker status
docker compose -f docker-compose.prod.yml ps
EOF

echo ""
echo "=================================================================="
echo "    ✔ ViScan Platform Successfully Deployed to ${SERVER}!         "
echo "    Gateway URL: http://16.192.134.200/                           "
echo "    Video Player: http://16.192.134.200/player/{report_id}        "
echo "=================================================================="
