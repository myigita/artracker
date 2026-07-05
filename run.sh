#!/usr/bin/env bash
# Starts the backend dev server. Extend this once frontend/ is scaffolded
# (e.g. run `npm run dev` in frontend/ alongside this, or use a process
# manager) — for now there's only a backend to start.
set -euo pipefail

cd "$(dirname "$0")/backend"

if [ ! -x ".venv/bin/uvicorn" ]; then
  echo "backend/.venv not found or missing uvicorn — set up the venv first." >&2
  exit 1
fi

exec .venv/bin/uvicorn app.main:app --reload
