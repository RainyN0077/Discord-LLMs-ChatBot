#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_DIR="$ROOT_DIR/.local-run"

stopped_any=0

stop_pid_file() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    stopped_any=1
    echo "Stopped ${name} (PID ${pid})"
  fi
  rm -f "$pid_file"
}

echo "[1/2] Stopping PID-file managed processes..."
stop_pid_file backend
stop_pid_file frontend

echo "[2/2] Stopping fallback local dev processes..."
pkill -f "uvicorn app.main:app.*--port 8093" >/dev/null 2>&1 && stopped_any=1 || true
pkill -f "vite.*--port 8094" >/dev/null 2>&1 && stopped_any=1 || true
pkill -f "npm run dev -- --host 0.0.0.0 --port 8094" >/dev/null 2>&1 && stopped_any=1 || true

if [[ "$stopped_any" -eq 0 ]]; then
  echo "No matching local dev process found."
else
  echo "Done."
fi
