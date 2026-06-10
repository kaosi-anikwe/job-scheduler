#!/usr/bin/env bash
# start_worker.sh — Start the Dilamme Job Scheduler worker process
#
# Usage:
#   ./deploy/start_worker.sh
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

echo "[start_worker] Starting worker process..."
exec uv run --package worker python -m worker
