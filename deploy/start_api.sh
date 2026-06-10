#!/usr/bin/env bash
# start_api.sh — Start the Dilamme Job Scheduler API server
#
# Usage:
#   ./deploy/start_api.sh
#
# Environment:
#   All settings are read from a .env file in the project root or from
#   environment variables already set in the shell/systemd unit.
#
# Requires: uv (https://docs.astral.sh/uv/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

cd "${BACKEND_DIR}"

echo "[start_api] Running database migrations..."
uv run alembic upgrade head

echo "[start_api] Starting API server..."
exec uv run --package api uvicorn api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --workers "${API_WORKERS:-2}" \
    --log-level "${LOG_LEVEL:-info}" \
    --no-access-log
