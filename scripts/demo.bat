@echo off
REM Demo on Windows: build UI, seed demo data, serve on http://localhost:8000
REM   scripts\demo.bat         use configured AI endpoints (e.g. Ollama)
REM   scripts\demo.bat --mock  use the bundled mock AI server (no models needed)
cd /d "%~dp0\.."
if "%APP_ENV%"=="" set APP_ENV=demo
pushd frontend && call npx vite build >nul && popd
cd backend
if "%1"=="--mock" (
  start "GMS mock AI" /min .venv\Scripts\python -m app.devtools.mock_ai --port 9100
  timeout /t 3 >nul
  .venv\Scripts\python -m app.seed use-mock-ai http://127.0.0.1:9100/v1
)
.venv\Scripts\python -m app.seed demo
echo Open http://localhost:8000   (doctor: ananya.rao@lifecaremedico.in / Clinic@2026)
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
