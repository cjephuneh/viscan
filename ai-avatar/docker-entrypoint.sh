#!/bin/bash
set -e

echo "=============================================================="
echo "    ViScan AI Avatar Service Container                        "
echo "=============================================================="

# If the command passed is 'test' or 'pytest', run tests directly
if [ "$1" = "test" ] || [ "$1" = "pytest" ]; then
    echo "[TEST SUITE] Executing full automated test cases..."
    exec pytest -v "${@:2}"
fi

# If RUN_TESTS_BEFORE_START is enabled, verify test suite before starting server
if [ "$RUN_TESTS_BEFORE_START" = "true" ] || [ "$RUN_TESTS_BEFORE_START" = "1" ]; then
    echo "[CI/CD CHECK] Running automated test cases before server startup..."
    if pytest -v; then
        echo "[CI/CD CHECK] All 22 test cases PASSED. Proceeding with server start..."
    else
        echo "[CI/CD CHECK ERROR] Test suite failed! Aborting server start to prevent deployment of broken code."
        exit 1
    fi
fi

# Default: execute the passed command (e.g. uvicorn)
echo "[STARTUP] Launching application on port ${APP_PORT:-9090}..."
exec "$@"
