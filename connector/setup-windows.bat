@echo off
title Fair Share - First Time Setup
cd /d "%~dp0"
echo ========================================
echo   iRacing Fair Share - Windows Setup
echo ========================================
echo.
where winget.exe >nul 2>nul
if errorlevel 1 (
  echo Windows Package Manager is missing.
  echo Install or update App Installer from the Microsoft Store, then run this again.
  pause
  exit /b 1
)
where py.exe >nul 2>nul
if errorlevel 1 (
  echo Installing Python...
  winget install --id Python.Python.3.13 --exact --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :failed
)
if not exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" if not exist "C:\Program Files\cloudflared\cloudflared.exe" (
  echo Installing Cloudflare Tunnel...
  winget install --id Cloudflare.cloudflared --exact --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :failed
)
echo.
echo Setup complete.
echo Close this window, then double-click start-connector.bat.
pause
exit /b 0
:failed
echo.
echo Setup did not finish. Check the error above and try again.
pause
exit /b 1

