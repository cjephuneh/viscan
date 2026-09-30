#!/usr/bin/env bash
# ==============================================================================
# ViScan pull-based deployer (runs ON the production server, e.g. gp5).
#
# Every run (systemd timer, every 2 min):
#   1. git fetch origin/<branch>
#   2. If the commit is already deployed          -> exit quietly
#   3. Ask GitHub whether the "ViScan CI" workflow -> not finished: wait
#      passed for that exact commit               -> failed:       skip + log
#                                                 -> passed:       deploy
#   4. git reset --hard, docker compose up --build -d, health check, prune
#
# No GitHub secret is needed: the repo is public and the server only *reads*
# the Actions API (unauthenticated, 60 req/h; we call it only for new commits).
#
# Usage:  server-deploy.sh [--force] [--skip-ci-check]
#   --force          redeploy even if the commit is already deployed
#   --skip-ci-check  deploy without waiting for GitHub Actions (emergency use)
#
# Config (env or /home/ubuntu/.viscan-deploy.env):
#   VISCAN_REPO_DIR   (default /home/ubuntu/viscan)
#   VISCAN_GH_REPO    (default cjephuneh/viscan)
#   VISCAN_BRANCH     (default main)
#   VISCAN_CI_CHECK   name of the check run to wait for (default "all tests passed")
#   GITHUB_TOKEN      optional, raises the API rate limit
# ==============================================================================
set -euo pipefail

main() {
    # Everything lives inside main() so bash parses the whole file before
    # running it: `git reset --hard` below rewrites this very script.
    [ -f /home/ubuntu/.viscan-deploy.env ] && . /home/ubuntu/.viscan-deploy.env

    local REPO_DIR="${VISCAN_REPO_DIR:-/home/ubuntu/viscan}"
    local GH_REPO="${VISCAN_GH_REPO:-cjephuneh/viscan}"
    local BRANCH="${VISCAN_BRANCH:-main}"
    local CI_CHECK="${VISCAN_CI_CHECK:-all tests passed}"
    local COMPOSE_FILE="docker-compose.prod.yml"
    local STATE_DIR="/home/ubuntu/.viscan-deploy"
    local LOG_FILE="$STATE_DIR/deploy.log"
    local DEPLOYED_FILE="$STATE_DIR/deployed-sha"
    local SKIPPED_FILE="$STATE_DIR/skipped-sha"
    local LOCK_FILE="$STATE_DIR/lock"
    local FORCE=false SKIP_CI=false

    for arg in "$@"; do
        case "$arg" in
            --force) FORCE=true ;;
            --skip-ci-check) SKIP_CI=true ;;
            *) echo "unknown option: $arg" >&2; exit 2 ;;
        esac
    done

    mkdir -p "$STATE_DIR"
    exec 9>"$LOCK_FILE"
    if ! flock -n 9; then
        echo "another deploy is running; exiting"; exit 0
    fi

    log() { printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG_FILE"; }

    # ---- 1. fetch ------------------------------------------------------------
    if [ ! -d "$REPO_DIR/.git" ]; then
        log "cloning $GH_REPO into $REPO_DIR"
        git clone "git@github.com:${GH_REPO}.git" "$REPO_DIR" \
            || git clone "https://github.com/${GH_REPO}.git" "$REPO_DIR"
    fi
    cd "$REPO_DIR"
    git fetch -q origin "$BRANCH"
    local TARGET DEPLOYED
    TARGET="$(git rev-parse "origin/$BRANCH")"
    DEPLOYED="$(cat "$DEPLOYED_FILE" 2>/dev/null || echo none)"

    if [ "$TARGET" = "$DEPLOYED" ] && [ "$FORCE" = false ]; then
        exit 0   # nothing new; stay silent so the log only shows real events
    fi
    if [ -f "$SKIPPED_FILE" ] && [ "$(cat "$SKIPPED_FILE")" = "$TARGET" ] && [ "$FORCE" = false ]; then
        exit 0   # already reported as failed CI; wait for a new commit
    fi

    # ---- 2. CI gate ----------------------------------------------------------
    if [ "$SKIP_CI" = false ]; then
        local auth=() api="https://api.github.com/repos/${GH_REPO}/commits/${TARGET}/check-runs?per_page=100"
        [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
        local json
        if ! json="$(curl -fsS --max-time 20 -H 'Accept: application/vnd.github+json' "${auth[@]}" "$api")"; then
            log "warning: GitHub API unreachable; will retry next tick (commit ${TARGET:0:7})"
            exit 0
        fi
        local status conclusion
        status="$(jq -r --arg n "$CI_CHECK" '[.check_runs[] | select(.name==$n)] | .[0].status // "missing"' <<<"$json")"
        conclusion="$(jq -r --arg n "$CI_CHECK" '[.check_runs[] | select(.name==$n)] | .[0].conclusion // ""' <<<"$json")"

        case "$status:$conclusion" in
            completed:success)
                log "CI passed for ${TARGET:0:7}; deploying" ;;
            completed:*)
                log "CI FAILED (${conclusion}) for ${TARGET:0:7}; NOT deploying. Fix and push again."
                echo "$TARGET" > "$SKIPPED_FILE"; exit 0 ;;
            missing:*)
                # Give Actions a few minutes to register the run before complaining.
                local age=$(( $(date +%s) - $(git show -s --format=%ct "$TARGET") ))
                if [ "$age" -gt 1800 ]; then
                    log "no '$CI_CHECK' check found for ${TARGET:0:7} after ${age}s; NOT deploying (is the CI workflow present?)"
                    echo "$TARGET" > "$SKIPPED_FILE"
                fi
                exit 0 ;;
            *)
                exit 0 ;;   # queued / in_progress -> try again next tick
        esac
    else
        log "CI check skipped by flag; deploying ${TARGET:0:7}"
    fi

    # ---- 3. update working tree ---------------------------------------------
    git checkout -q "$BRANCH"
    git reset -q --hard "$TARGET"
    log "checked out $(git log -1 --format='%h %s')"

    for f in .env ai-interpreter/.env ai-avatar/.env backend/.env; do
        if [ ! -f "$f" ]; then
            log "warning: $f missing; creating from ${f}.example - fill in the real values!"
            cp "${f}.example" "$f"
        fi
    done

    # ---- 4. build & start ----------------------------------------------------
    log "docker compose up --build (this can take a few minutes)"
    if ! docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans >>"$LOG_FILE" 2>&1; then
        log "ERROR: docker compose up failed for ${TARGET:0:7}; see $LOG_FILE"
        echo "$TARGET" > "$SKIPPED_FILE"; exit 1
    fi

    # ---- 5. health check -----------------------------------------------------
    local ok=false
    for _ in $(seq 1 30); do
        if curl -fsS --max-time 3 http://localhost/health >/dev/null 2>&1 \
           && curl -fsS --max-time 3 http://localhost/api/v1/health  >/dev/null 2>&1 \
           && curl -fsS --max-time 3 http://localhost/api/v1/health/ >/dev/null 2>&1; then
            ok=true; break
        fi
        sleep 5
    done
    docker compose -f "$COMPOSE_FILE" ps --format 'table {{.Name}}\t{{.Status}}' | tee -a "$LOG_FILE"
    if [ "$ok" = true ]; then
        echo "$TARGET" > "$DEPLOYED_FILE"; rm -f "$SKIPPED_FILE"
        log "deploy of ${TARGET:0:7} HEALTHY"
    else
        log "ERROR: services did not become healthy after deploy of ${TARGET:0:7}"
        echo "$TARGET" > "$SKIPPED_FILE"
    fi

    docker image prune -f >/dev/null 2>&1 || true
    [ "$ok" = true ]
}

main "$@"
