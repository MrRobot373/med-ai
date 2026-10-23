#!/usr/bin/env bash
# One-time setup: Python venv + dependencies, frontend dependencies, .env
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
[ -f .env ] || { cp .env.example .env; sed -i.bak "s/^APP_SECRET_KEY=.*/APP_SECRET_KEY=$($PY -c 'import secrets;print(secrets.token_urlsafe(48))')/" .env && rm -f .env.bak; echo "Created .env with a fresh secret key"; }
$PY -m venv backend/.venv
backend/.venv/bin/pip install -q --upgrade pip
backend/.venv/bin/pip install -q -e "backend[dev]"
(cd frontend && npm ci --no-audit --no-fund)
echo "Setup complete. Next: scripts/demo.sh (demo) or scripts/dev.sh (development)."
