@echo off
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
    echo backend\.venv not found. Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

backend\.venv\Scripts\python.exe scripts\health_check.py
