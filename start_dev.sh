#!/usr/bin/env bash

set -euo pipefail

# Start backend (FastAPI via Poetry) and frontend (Vite via pnpm) in parallel.
# - Kills anything on ports 8000 (backend) and 5173 (frontend)
# - Writes logs to backend.out.log and frontend.out.log at repo root
# - Opens the app in the browser once ready
# - Tails logs; press Ctrl+C to stop both

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_LOG="$ROOT_DIR/backend.out.log"
FRONTEND_LOG="$ROOT_DIR/frontend.out.log"

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [[ -n "${pids:-}" ]]; then
    echo "Killing processes on port $port: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local timeout="${3:-40}"
  local start
  start=$(date +%s)
  echo "Waiting for $name at $url ..."
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is up."
      break
    fi
    local now
    now=$(date +%s)
    if (( now - start > timeout )); then
      echo "Timed out waiting for $name at $url after ${timeout}s"
      break
    fi
    sleep 1
  done
}

echo "Repo root: $ROOT_DIR"

echo "Ensuring ports are free..."
kill_port 8000
kill_port 5173

echo "Clearing logs..."
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

echo "Starting backend on :8000..."
(
  cd "$BACKEND_DIR"
  # Prefer Azure Postgres via AAD token if configured; else fall back to Supabase
  if [[ -f "$BACKEND_DIR/.env.azure" ]]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "$BACKEND_DIR/.env.azure" | xargs)
    if command -v az >/dev/null 2>&1; then
      TOKEN=$(az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken -o tsv || true)
      if [[ -n "${TOKEN:-}" && -n "${PGHOST:-}" && -n "${PGUSER:-}" && -n "${PGDATABASE:-}" ]]; then
        export DATABASE_URL="postgresql+psycopg2://${PGUSER}:${TOKEN}@${PGHOST}:5432/${PGDATABASE}?sslmode=require"
        echo "Using Azure PostgreSQL (AAD token)"
      else
        echo "Azure DB env incomplete, falling back to other envs" >&2
      fi
    else
      echo "Azure CLI not found; cannot obtain AAD token. Install az or use another env." >&2
    fi
  fi
  # Fallback: Supabase local env
  if [[ -z "${DATABASE_URL:-}" && -f "$BACKEND_DIR/.env.supabase" ]]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "$BACKEND_DIR/.env.supabase" | xargs)
    echo "Using Supabase DATABASE_URL"
  fi
  # Best-effort dependency ensure; ignore failure to avoid blocking startup if poetry not available
  if command -v poetry >/dev/null 2>&1; then
    poetry run uvicorn do_not_call.main:app --host 0.0.0.0 --port 8000 --reload
  else
    echo "Poetry not found. Please install Poetry or start backend manually." >&2
    exit 127
  fi
) >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$ROOT_DIR/backend.pid"

echo "Starting frontend on :5173..."
(
  cd "$FRONTEND_DIR"
  if command -v pnpm >/dev/null 2>&1; then
    pnpm dev
  else
    echo "pnpm not found. Please install pnpm (https://pnpm.io/) or start frontend manually." >&2
    exit 127
  fi
) >> "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$ROOT_DIR/frontend.pid"

cleanup() {
  echo
  echo "Stopping dev servers..."
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup INT TERM

# Wait for services
wait_for_http "http://localhost:8000/docs" "Backend (FastAPI)"
wait_for_http "http://localhost:5173/" "Frontend (Vite)"

# Open browser (macOS)
if command -v open >/dev/null 2>&1; then
  open "http://localhost:5173/" || true
fi

echo
echo "Both servers started. Tailing logs (Ctrl+C to stop):"
echo "  Backend log:   $BACKEND_LOG"
echo "  Frontend log:  $FRONTEND_LOG"
echo
tail -n +1 -f "$BACKEND_LOG" "$FRONTEND_LOG"


