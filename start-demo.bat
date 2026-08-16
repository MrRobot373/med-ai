@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  GMS Clinical AI - start-demo (Phase 14 - spec section 86)
echo ============================================================
echo Brings up Qdrant (and SearXNG if Research Mode is enabled),
echo verifies Ollama/the configured model, warms the generation/
echo embedding/reranker models, runs migrations, seeds demo
echo accounts/patients/reports (ingested through the real
echo pipeline) and the reference knowledge base, then starts the
echo backend/frontend with real health polling. The browser only
echo opens once the backend is actually responding.
echo.

if not exist backend\.venv\Scripts\python.exe (
    echo FAIL: backend\.venv not found. Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo [1/15] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo   FAIL: Docker does not appear to be running. Start Docker Desktop and re-run this script.
    exit /b 1
)
echo   OK

echo [2/15] Starting Qdrant...
docker compose up -d qdrant
if errorlevel 1 (
    echo   FAIL: could not start Qdrant. See docker compose output above.
    exit /b 1
)
echo   OK

echo [3/15] Checking whether Research Mode's optional SearXNG should start...
set RESEARCH_ENABLED=0
if exist .env (
    findstr /r /i "^ENABLE_RESEARCH *= *true" .env >nul 2>&1
    if not errorlevel 1 set RESEARCH_ENABLED=1
)
if "%RESEARCH_ENABLED%"=="1" (
    echo   ENABLE_RESEARCH=true in .env - starting SearXNG...
    docker compose --profile research up -d searxng
    if errorlevel 1 (
        echo   WARNING: could not start SearXNG. Research Mode's general-web source will be unavailable; PubMed/FDA/ClinicalTrials.gov are unaffected.
    ) else (
        echo   OK
    )
) else (
    echo   SKIP: Research Mode is not enabled (no ENABLE_RESEARCH=true in .env). Not starting SearXNG.
)

echo [4/15] Checking Ollama...
curl -s -m 5 http://localhost:11434/api/version >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Ollama does not appear to be reachable at http://localhost:11434.
    echo   Local AI features will be degraded until it is running.
) else (
    echo   OK
)

echo [5/15] Running database migrations...
pushd backend
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo   FAIL: migrations failed.
    popd
    exit /b 1
)
popd
echo   OK

echo [6/15] Seeding demo accounts...
backend\.venv\Scripts\python.exe scripts\seed_demo.py
if errorlevel 1 (
    echo   FAIL: seeding demo accounts failed.
    exit /b 1
)
echo   OK

echo [7/15] Seeding demo patients (5 synthetic ophthalmology patients, spec section 88)...
backend\.venv\Scripts\python.exe scripts\seed_demo_patients.py
if errorlevel 1 (
    echo   FAIL: seeding demo patients failed.
    exit /b 1
)
echo   OK

echo [8/15] Generating sample report files for upload/reconciliation demos...
backend\.venv\Scripts\python.exe scripts\generate_sample_reports.py
if errorlevel 1 (
    echo   FAIL: generating sample reports failed.
    exit /b 1
)
echo   OK

echo [9/15] Ingesting sample reports into demo patients (real extraction/OCR/vision pipeline)...
backend\.venv\Scripts\python.exe scripts\seed_demo_reports.py
if errorlevel 1 (
    echo   WARNING: seeding demo reports failed - patient records will have less data until "python scripts\seed_demo_reports.py" is re-run successfully. Not fatal to the rest of the demo.
) else (
    echo   OK
)

echo [10/15] Ingesting reference clinical guidelines into the RAG knowledge base...
echo   (Already-indexed, unchanged content is skipped - only the first run per file is slow.)
backend\.venv\Scripts\python.exe scripts\ingest_knowledge.py
if errorlevel 1 (
    echo   WARNING: knowledge ingestion failed - guideline Q^&A will have no
    echo   evidence to retrieve until "python scripts\ingest_knowledge.py" is
    echo   re-run successfully. Not fatal to the rest of the demo.
) else (
    echo   OK
)

echo [11/15] Warming the generation/embedding/reranker models...
echo   (First CPU load of each model - can take up to a minute or two.)
backend\.venv\Scripts\python.exe scripts\warm_models.py
echo   Done (warm-up failures are non-fatal - the next step is the real readiness check).

echo [12/15] Verifying full system health...
backend\.venv\Scripts\python.exe scripts\health_check.py
if errorlevel 1 (
    echo   WARNING: one or more components reported unhealthy above. The demo will
    echo   still start, but affected features will show a real degraded state
    echo   rather than pretending to work (spec section 85).
) else (
    echo   OK - all components healthy.
)

echo [13/15] Starting backend and frontend...
start "GMS Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "GMS Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo [14/15] Waiting for backend health...
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

echo [15/15] Opening the browser now that critical services are healthy...
echo.
echo Demo account credentials: data\sqlite\.demo_credentials.txt
echo Sample report files to upload (identity-mismatch demo): data\sample_reports\mismatch_example_different_patient.pdf
echo Run "python scripts\health_check.py" any time for full dependency status.
start "" http://localhost:5173
echo Done. Frontend: http://localhost:5173  Backend docs: http://localhost:8000/docs
endlocal
