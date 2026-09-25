@echo off
title iRacing Fair Share Connector
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3 from python.org first.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating the connector environment...
  py -3 -m venv .venv
  call .venv\Scripts\python.exe -m pip install --upgrade pip
)
call .venv\Scripts\python.exe -m pip install -q -r requirements.txt
set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if exist "%CLOUDFLARED%" (
  start "Fair Share Public Tunnel" "%CLOUDFLARED%" tunnel --url http://127.0.0.1:8080 --no-autoupdate
) else (
  echo Cloudflare Tunnel is not installed. Local mode will still work.
)
call .venv\Scripts\python.exe iracing_connector.py
if errorlevel 1 pause

