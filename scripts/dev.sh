#!/usr/bin/env bash
# Development: API with auto-reload on :8000 and the Vite dev server on :5173
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
wait
