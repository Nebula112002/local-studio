#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="${LOCAL_STUDIO_PORT:-8787}"
PYTHON=".venv/bin/python"
LOCK_FILE=".local-studio.lock"
LOG_FILE="local-studio.log"
TAILNET_HOSTNAME="${LOCAL_STUDIO_TAILNET_HOSTNAME:-calebscomputer.tailfdadcb.ts.net}"
QUIET="${LOCAL_STUDIO_AUTOSTART:-0}"
DEV="${LOCAL_STUDIO_DEV:-0}"

log() {
  local line="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$line" >> "$LOG_FILE"
  [[ "$QUIET" != "1" ]] && echo "$*"
}

is_listening() {
  ss -ltn 2>/dev/null | grep -q "127.0.0.1:${PORT}" || \
  netstat -ltn 2>/dev/null | grep -q "127.0.0.1:${PORT}"
}

if [[ -f "$LOCK_FILE" ]]; then
  lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || true)
  if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null && is_listening; then
    log "Local Studio already running (PID $lock_pid)"
    exit 0
  fi
fi

if is_listening; then
  log "Local Studio is already running on http://127.0.0.1:${PORT}"
  log "Tailnet: https://${TAILNET_HOSTNAME}:${PORT}"
  exit 0
fi

echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

log "Local Studio — starting..."

if [[ ! -x "$PYTHON" ]]; then
  log "Creating virtual environment..."
  python3 -m venv .venv
fi

if [[ ! -x "$PYTHON" ]]; then
  log "ERROR: Python not found. Install Python 3.10+."
  exit 1
fi

if [[ "$QUIET" != "1" ]]; then
  "$PYTHON" -m pip install -q -r requirements.txt 2>/dev/null || true
fi

UVICORN_ARGS=(-m uvicorn server.main:app --host 127.0.0.1 --port "$PORT")
[[ "$DEV" == "1" || "${1:-}" == "--dev" ]] && UVICORN_ARGS+=(--reload)

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "  Local Studio is ready"
log ""
log "  Local:   http://127.0.0.1:${PORT}"
log "  Tailnet: https://${TAILNET_HOSTNAME}:${PORT}"
log ""
log "  Start ComfyUI or Forge in Stability Matrix first."
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""

# Open browser on Linux/macOS if not quiet
if [[ "$QUIET" != "1" ]]; then
  (sleep 1 && (xdg-open "http://127.0.0.1:${PORT}" 2>/dev/null || open "http://127.0.0.1:${PORT}" 2>/dev/null || true)) &
fi

if [[ "$QUIET" == "1" ]]; then
  exec "$PYTHON" "${UVICORN_ARGS[@]}" >> "$LOG_FILE" 2>&1
else
  exec "$PYTHON" "${UVICORN_ARGS[@]}"
fi
