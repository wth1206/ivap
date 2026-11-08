@echo off
setlocal
set "ROOT=%~dp0.."
"%ROOT%\.mysql\mysql-8.0.28-winx64\bin\mysqladmin.exe" --defaults-file="%ROOT%\.mysql\client.ini" ping
