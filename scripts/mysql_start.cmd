@echo off
setlocal
set "ROOT=%~dp0.."
netstat -ano | findstr /R /C:":3306 .*LISTENING" >nul
if not errorlevel 1 (
  echo MySQL is already listening on 127.0.0.1:3306.
  exit /b 0
)
echo Starting IVAP MySQL 8.0.28 on 127.0.0.1:3306 ...
echo Press Ctrl+C to stop. Data directory: %ROOT%\.mysql\data
"%ROOT%\.mysql\mysql-8.0.28-winx64\bin\mysqld.exe" --defaults-file="%ROOT%\.mysql\my.ini" --console
