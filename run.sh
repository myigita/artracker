#!/usr/bin/env bash
# Starts both dev servers: the FastAPI backend on :8000 and Vite on :5173.
#
# Browse to http://localhost:5173 — never :8000. Vite proxies /api to the
# backend, which keeps the app same-origin and means no CORS config.
#
# Ctrl-C stops both. So does either one crashing: `wait -n` returns as soon as
# the first process exits, and the EXIT trap takes the survivor down with it.
# Without that you'd be left with a half-running app and a stale port.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x "backend/.venv/bin/uvicorn" ]; then
  echo "backend/.venv not found or missing uvicorn. Set it up with:" >&2
  echo "  python -m venv backend/.venv" >&2
  echo "  backend/.venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

if [ ! -x "frontend/node_modules/.bin/vite" ]; then
  echo "frontend deps not installed. Set them up with:" >&2
  echo "  npm --prefix frontend install" >&2
  exit 1
fi

pids=()

cleanup() {
  # Clear the traps first so a second Ctrl-C during shutdown doesn't re-enter.
  trap - INT TERM EXIT
  kill "${pids[@]}" 2>/dev/null || true
  wait "${pids[@]}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Each server runs from its own directory. uvicorn needs backend/ on the path
# for `app.main`, and the default DATABASE_URL is relative — started from the
# repo root it would create a second, empty artracker.db in the wrong place.
(cd backend && exec .venv/bin/uvicorn app.main:app --reload) &
pids+=($!)

# vite directly rather than `npm run dev`: npm would sit in the middle as a
# wrapper process, and killing it can orphan the vite child it spawned.
(cd frontend && exec node_modules/.bin/vite) &
pids+=($!)

echo
echo "  backend  http://localhost:8000"
echo "  app      http://localhost:5173   <- open this one"
echo

# Returns as soon as EITHER server exits; the EXIT trap stops the other.
wait -n
