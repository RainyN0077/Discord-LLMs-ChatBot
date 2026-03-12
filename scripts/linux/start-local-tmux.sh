#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib-local.sh"

if ! command -v tmux >/dev/null 2>&1; then
  echo "[ERROR] tmux not found. Install tmux or use start-local-nohup.sh."
  exit 1
fi

SESSION_NAME="${TMUX_SESSION_NAME:-discord-llm-local}"

echo "[1/3] Preparing dependencies..."
ensure_backend_env
ensure_frontend_deps

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "[2/3] Killing existing tmux session: $SESSION_NAME"
  tmux kill-session -t "$SESSION_NAME"
fi

echo "[3/3] Starting tmux session: $SESSION_NAME"
tmux new-session -d -s "$SESSION_NAME" -n backend "cd '$ROOT_DIR' && '$SCRIPT_DIR/run-backend-local.sh'"
if command -v npm >/dev/null 2>&1; then
  tmux new-window -t "$SESSION_NAME" -n frontend "cd '$ROOT_DIR' && '$SCRIPT_DIR/run-frontend-local.sh'"
fi

echo "Started in tmux."
echo "Backend:  http://localhost:${BACKEND_PORT}"
echo "Frontend: http://localhost:${FRONTEND_PORT}"
echo "Attach:   tmux attach -t ${SESSION_NAME}"
