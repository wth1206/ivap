@echo off
setlocal
cd /d "%~dp0.."
docker compose --env-file .env.docker ps
echo.
docker compose --env-file .env.docker logs --tail=120 backend
