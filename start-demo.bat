@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  GMS Clinical AI — start-demo (Phase 01 minimal version)
echo ============================================================
echo NOTE: this is the Foundation-phase startup script. It brings
echo up Qdrant, runs migrations, and starts the backend/frontend
echo with real health polling. The full 15-step sequence from
echo spec section 86 (SearXNG, model warm-up, seed-data checks,
echo etc.) is added as those phases are built.
echo.

echo [1/6] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo   FAIL: Docker does not appear to be running. Start Docker Desktop and re-run this script.
    exit /b 1
)
echo   OK

echo [2/6] Starting Qdrant...
docker compose up -d qdrant
if errorlevel 1 (
    echo   FAIL: could not start Qdrant. See docker compose output above.
    exit /b 1
)
echo   OK

echo [3/6] Checking Ollama...
curl -s -m 5 http://localhost:11434/api/version >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Ollama does not appear to be reachable at http://localhost:11434.
    echo   Local AI features will be degraded until it is running.
) else (
    echo   OK
)

echo [4/6] Running database migrations...
if not exist backend\.venv\Scripts\python.exe (
    echo   FAIL: backend\.venv not found. Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)
pushd backend
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo   FAIL: migrations failed.
    popd
    exit /b 1
)
popd
echo   OK

echo [5/6] Starting backend and frontend...
start "GMS Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "GMS Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo [6/6] Waiting for backend health...
set /a attempts=0
:poll
set /a attempts+=1
curl -s -m 3 http://localhost:8000/api/health >nul 2>&1
if not errorlevel 1 goto ready
if %attempts% GEQ 30 (
    echo   FAIL: backend did not become healthy in time. Check the "GMS Backend" window.
    exit /b 1
)
timeout /t 2 >nul
goto poll

:ready
echo   OK — backend is responding.
echo.
echo Run "python scripts\health_check.py" for full dependency status.
start "" http://localhost:5173
echo Done. Frontend: http://localhost:5173  Backend docs: http://localhost:8000/docs
endlocal
