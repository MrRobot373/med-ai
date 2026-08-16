@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  GMS Clinical AI - reset-demo (spec section 87)
echo ============================================================
echo This PERMANENTLY DELETES the current demo database, all
echo uploaded/knowledge files, and all Qdrant collection points,
echo then re-seeds a fresh known-clean demo state: accounts,
echo synthetic patients, sample reports (ingested through the real
echo pipeline), and the reference knowledge base.
echo.
echo This only ever touches this machine's locally configured demo
echo environment (DATABASE_URL / UPLOAD_DIR) - there is no
echo multi-tenant/production mode in this build to accidentally hit.
echo.

if not exist backend\.venv\Scripts\python.exe (
    echo FAIL: backend\.venv not found. Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

set /p CONFIRM="Type YES to permanently delete and reset the demo: "
if /i not "%CONFIRM%"=="YES" (
    echo Aborted - nothing was deleted.
    exit /b 1
)

echo.
echo Stopping any running backend/frontend so the database file isn't locked...
call stop-demo.bat >nul 2>&1

echo Running reset...
backend\.venv\Scripts\python.exe scripts\reset_demo.py --yes
if errorlevel 1 (
    echo   FAIL: reset did not complete successfully. See output above.
    exit /b 1
)

echo.
echo Done. Run start-demo.bat to launch the freshly reset demo.
endlocal
