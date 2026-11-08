@echo off
setlocal
cd /d "%~dp0.."
echo Starting IVAP backend on http://127.0.0.1:8000 ...
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
