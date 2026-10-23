#!/usr/bin/env bash
# Demo: build the UI, seed staff, the 15 patient files + knowledge packs, serve everything on :8000.
#   scripts/demo.sh            use the AI endpoints configured in Settings / .env (e.g. Ollama)
#   scripts/demo.sh --mock     use the bundled mock AI server (no GPU or models needed)
set -euo pipefail
cd "$(dirname "$0")/.."
export APP_ENV=${APP_ENV:-demo}
trap 'kill 0' EXIT
(cd frontend && npx vite build >/dev/null) && echo "UI built"
cd backend
if [[ "${1:-}" == "--mock" ]]; then
  .venv/bin/python -m app.devtools.mock_ai --port 9100 >/dev/null 2>&1 &
  sleep 2
  .venv/bin/python -m app.seed use-mock-ai http://127.0.0.1:9100/v1
fi
.venv/bin/python -m app.seed demo
echo "Open http://localhost:8000  (doctor: ananya.rao@gmsclinic.local / Clinic@2026, front desk: meera.pillai@gmsclinic.local / Desk@2026)"
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
