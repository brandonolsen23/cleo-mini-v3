#!/usr/bin/env bash
# ============================================================================
# Cleo Mini V3 — Dev Environment
#
# Starts both the FastAPI backend (port 8099, auto-reload) and the Vite
# frontend dev server (port 5173, proxies /api to 8099).
#
# Usage:   ./dev.sh
# Open:    http://localhost:5173       (ALWAYS use this port)
# Admin:   http://localhost:5173/admin
# Stop:    Ctrl+C (kills both processes)
# ============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "ERROR: No .venv found. Run: python3 -m venv .venv && pip install -e ."
  exit 1
fi

# Kill any leftover processes on our ports
for port in 8099 5173; do
  lsof -ti:$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done
sleep 1

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  wait 2>/dev/null
  echo "Done."
  exit 0
}
trap cleanup INT TERM

# --- Backend (FastAPI + uvicorn, auto-reload on Python changes) ---
echo "Starting backend on :8099 (auto-reload)..."
cd "$DIR"
"$VENV_PYTHON" -m uvicorn cleo.web.app:app \
  --host 127.0.0.1 \
  --port 8099 \
  --reload \
  --reload-dir cleo \
  --log-level warning &
BACKEND_PID=$!

# --- Frontend (Vite dev server, proxies /api to :8099) ---
echo "Starting frontend on :5173..."
cd "$DIR/frontend"
npx vite --port 5173 --clearScreen false &
FRONTEND_PID=$!

sleep 2
echo ""
echo "================================================"
echo "  Dev environment ready"
echo "  Open:  http://localhost:5173"
echo "  Admin: http://localhost:5173/admin"
echo "  Ctrl+C to stop both"
echo "================================================"
echo ""

# Wait forever until Ctrl+C
wait
