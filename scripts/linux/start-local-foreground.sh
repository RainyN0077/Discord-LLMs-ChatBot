#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib-local.sh"

echo "[1/3] Preparing dependencies..."
ensure_backend_env
ensure_frontend_deps

echo "[2/3] Starting backend..."
"$SCRIPT_DIR/run-backend-local.sh" &
BACKEND_PID=$!

cleanup() {
  if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if command -v npm >/dev/null 2>&1; then
  echo "[3/3] Starting frontend in foreground..."
  "$SCRIPT_DIR/run-frontend-local.sh"
else
  echo "[3/3] npm not found, running backend only."
  wait "$BACKEND_PID"
fi
