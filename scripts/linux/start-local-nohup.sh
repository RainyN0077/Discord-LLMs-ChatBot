#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib-local.sh"

PID_DIR="$ROOT_DIR/.local-run"
LOG_DIR="$ROOT_DIR/.local-run/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

echo "[1/4] Preparing dependencies..."
ensure_backend_env
ensure_frontend_deps

echo "[2/4] Stopping previous local processes if any..."
"$SCRIPT_DIR/stop-local.sh" >/dev/null 2>&1 || true

echo "[3/4] Starting backend in background (nohup)..."
nohup "$SCRIPT_DIR/run-backend-local.sh" >"$LOG_DIR/backend.log" 2>&1 &
echo $! >"$PID_DIR/backend.pid"

if command -v npm >/dev/null 2>&1; then
  echo "[4/4] Starting frontend in background (nohup)..."
  nohup "$SCRIPT_DIR/run-frontend-local.sh" >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$PID_DIR/frontend.pid"
else
  echo "[4/4] npm not found, skipped frontend startup."
fi

echo "Started."
echo "Backend:  http://localhost:${BACKEND_PORT}"
echo "Frontend: http://localhost:${FRONTEND_PORT}"
echo "Logs:     $LOG_DIR"
