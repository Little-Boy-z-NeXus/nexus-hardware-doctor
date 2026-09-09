@echo off
setlocal EnableExtensions
title NeXus - First-time setup
cd /d "%~dp0"

echo [NeXus] Preparing backend, frontend, and firmware tools...

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.11 was not found in PATH.
  goto :failed
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [NeXus] Creating backend virtual environment...
  python -m venv "backend\.venv"
  if errorlevel 1 goto :failed
)

set "NEXUS_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
echo [NeXus] Installing backend dependencies...
"%NEXUS_PYTHON%" -m pip install -e ".\backend[dev]"
if errorlevel 1 goto :failed

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js and npm were not found in PATH.
  goto :failed
)

echo [NeXus] Installing frontend dependencies...
pushd "frontend"
if exist "package-lock.json" (
  call npm ci
) else (
  call npm install
)
if errorlevel 1 (
  popd
  goto :failed
)
if not exist ".env.local" copy /Y ".env.example" ".env.local" >nul
popd

where pio >nul 2>&1
if errorlevel 1 (
  echo [NeXus] Installing PlatformIO...
  python -m pip install platformio
  if errorlevel 1 goto :failed
)

echo.
echo [SUCCESS] NeXus setup is complete.
echo Double-click nexus-start-app.cmd to open the web application.
echo Double-click nexus-run-firmware.cmd to upload and monitor the ESP32-S3.
if not defined NEXUS_NO_PAUSE pause
exit /b 0

:failed
echo.
echo [ERROR] Setup did not complete. Read the message above, then run this file again.
if not defined NEXUS_NO_PAUSE pause
exit /b 1
