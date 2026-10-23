@echo off
REM One-time setup on Windows: Python venv + dependencies, frontend dependencies, .env
cd /d "%~dp0\.."
if not exist .env (
  copy .env.example .env >nul
  for /f %%k in ('python -c "import secrets;print(secrets.token_urlsafe(48))"') do powershell -Command "(Get-Content .env) -replace '^APP_SECRET_KEY=.*','APP_SECRET_KEY=%%k' | Set-Content .env"
  echo Created .env with a fresh secret key
)
python -m venv backend\.venv || goto :error
backend\.venv\Scripts\python -m pip install -q --upgrade pip
backend\.venv\Scripts\pip install -q -e "backend[dev]" || goto :error
pushd frontend && call npm ci --no-audit --no-fund && popd || goto :error
echo Setup complete. Next: scripts\demo.bat (add --mock to run without AI models)
exit /b 0
:error
echo Setup failed. & exit /b 1
