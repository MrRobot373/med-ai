@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  GMS Clinical AI - start-demo (Phase 05 version)
echo ============================================================
echo NOTE: this brings up Qdrant, runs migrations, seeds demo
echo accounts/patients/sample reports, and starts the backend/
echo frontend with real health polling. The full 15-step sequence
echo from spec section 86 (SearXNG, model warm-up, etc.) is added
echo as those later phases are built.
echo.

echo [1/9] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo   FAIL: Docker does not appear to be running. Start Docker Desktop and re-run this script.
    exit /b 1
)
echo   OK

echo [2/9] Starting Qdrant...
docker compose up -d qdrant
if errorlevel 1 (
    echo   FAIL: could not start Qdrant. See docker compose output above.
    exit /b 1
)
echo   OK

echo [3/9] Checking Ollama...
curl -s -m 5 http://localhost:11434/api/version >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Ollama does not appear to be reachable at http://localhost:11434.
    echo   Local AI features will be degraded until it is running.
) else (
    echo   OK
)

if not exist backend\.venv\Scripts\python.exe (
    echo   FAIL: backend\.venv not found. Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo [4/9] Running database migrations...
pushd backend
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo   FAIL: migrations failed.
    popd
    exit /b 1
)
popd
echo   OK

echo [5/9] Seeding demo accounts...
backend\.venv\Scripts\python.exe scripts\seed_demo.py
if errorlevel 1 (
    echo   FAIL: seeding demo accounts failed.
    exit /b 1
)
echo   OK

echo [6/9] Seeding demo patients...
backend\.venv\Scripts\python.exe scripts\seed_demo_patients.py
if errorlevel 1 (
    echo   FAIL: seeding demo patients failed.
    exit /b 1
)
echo   OK

echo [7/9] Generating sample report files for upload demos...
backend\.venv\Scripts\python.exe scripts\generate_sample_reports.py
if errorlevel 1 (
    echo   FAIL: generating sample reports failed.
    exit /b 1
)
echo   OK

echo [8/9] Starting backend and frontend...
start "GMS Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "GMS Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo [9/9] Waiting for backend health...
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
echo   OK - backend is responding.
echo.
echo Demo account credentials: data\sqlite\.demo_credentials.txt
echo Sample report files to upload: data\sample_reports\
echo Run "python scripts\health_check.py" for full dependency status.
start "" http://localhost:5173
echo Done. Frontend: http://localhost:5173  Backend docs: http://localhost:8000/docs
endlocal
