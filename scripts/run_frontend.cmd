@echo off
setlocal
cd /d "%~dp0..\frontend"
echo Starting IVAP frontend at http://127.0.0.1:5173
echo Keep this window open. Press Ctrl+C to stop.
call npm.cmd run dev
