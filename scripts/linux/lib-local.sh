#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

BACKEND_PORT="${BACKEND_PORT:-8093}"
FRONTEND_PORT="${FRONTEND_PORT:-8094}"
VITE_API_PROXY_TARGET="${VITE_API_PROXY_TARGET:-http://localhost:${BACKEND_PORT}}"

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  echo "[ERROR] Python not found. Install Python 3.10+ and retry." >&2
  return 1
}

ensure_backend_env() {
  local py_cmd
  py_cmd="$(find_python)"
  if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "[setup] Creating virtual environment at $VENV_DIR"
    "$py_cmd" -m venv "$VENV_DIR"
  fi

  echo "[setup] Installing backend dependencies"
  "$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
  "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"
}

ensure_frontend_deps() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "[WARN] npm not found, skipping frontend dependency install."
    return 0
  fi
  echo "[setup] Installing frontend dependencies"
  (cd "$FRONTEND_DIR" && npm install)
}
