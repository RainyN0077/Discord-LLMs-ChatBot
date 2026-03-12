#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8093}"
FRONTEND_PORT="${FRONTEND_PORT:-8094}"
export VITE_API_PROXY_TARGET="${VITE_API_PROXY_TARGET:-http://localhost:${BACKEND_PORT}}"

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm not found. Install Node.js and npm first."
  exit 1
fi

cd "$FRONTEND_DIR"
exec npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
