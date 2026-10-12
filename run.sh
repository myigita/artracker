#!/usr/bin/env bash
# Starts both dev servers; open http://localhost:5173. Ctrl-C, or either one exiting, stops both.
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
  trap - INT TERM EXIT
  kill "${pids[@]}" 2>/dev/null || true
  wait "${pids[@]}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Run from backend/: the default DATABASE_URL is relative.
(cd backend && exec .venv/bin/uvicorn app.main:app --reload) &
pids+=($!)

# vite directly: killing an npm wrapper can orphan its child.
(cd frontend && exec node_modules/.bin/vite) &
pids+=($!)

echo
echo "  backend  http://localhost:8000"
echo "  app      http://localhost:5173   <- open this one"
echo

wait -n
