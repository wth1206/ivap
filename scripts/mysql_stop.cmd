@echo off
setlocal
set "ROOT=%~dp0.."
"%ROOT%\.mysql\mysql-8.0.28-winx64\bin\mysqladmin.exe" --defaults-file="%ROOT%\.mysql\client.ini" shutdown
if errorlevel 1 (
  echo Failed to stop MySQL. Is it running? Check %ROOT%\.mysql\mysql-error.log
  exit /b 1
)
echo MySQL stopped.
