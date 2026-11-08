@echo off
setlocal
cd /d "%~dp0.."
if not exist ".env.docker" (
  echo Missing .env.docker
  echo Copy .env.docker.example to .env.docker and fill the secrets first.
  exit /b 1
)
echo Starting IVAP containers (mysql + backend + frontend)...
docker compose --env-file .env.docker up -d --build
if errorlevel 1 exit /b 1
docker compose --env-file .env.docker ps
echo.
echo Frontend: http://localhost:8080
echo API docs:  http://localhost:8000/docs
