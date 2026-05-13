#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
BACKEND_PORT="${BACKEND_PORT:-8093}"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "[ERROR] Missing virtualenv python: $VENV_PYTHON"
  echo "Run one of the start-local scripts first."
  exit 1
fi

cd "$BACKEND_DIR"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export FAIL_ON_REDIS_ERROR="${FAIL_ON_REDIS_ERROR:-false}"

exec "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload --no-use-colors
