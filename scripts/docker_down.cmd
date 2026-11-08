@echo off
setlocal
cd /d "%~dp0.."
echo Stopping IVAP containers (data volumes are kept)...
docker compose --env-file .env.docker down
