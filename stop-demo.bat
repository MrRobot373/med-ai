@echo off
cd /d "%~dp0"

echo Stopping GMS Clinical AI demo services...

echo - Stopping Qdrant (docker compose)...
docker compose stop qdrant >nul 2>&1

echo - Stopping SearXNG if it was running (Research Mode's optional service)...
docker compose --profile research stop searxng >nul 2>&1

echo - Closing backend/frontend windows...
taskkill /FI "WINDOWTITLE eq GMS Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GMS Frontend*" /T /F >nul 2>&1

echo Done. (Qdrant data volume is preserved; use reset-demo.bat to clear demo state.)
