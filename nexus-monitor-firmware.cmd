@echo off
setlocal EnableExtensions
title NeXus ESP32-S3 Serial Monitor
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  goto :failed
)
where pio >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PlatformIO was not found. Double-click nexus-setup.cmd first.
  goto :failed
)

set "NEXUS_PORT="
for /f "usebackq delims=" %%P in (`python "%~dp0scripts\nexus-detect-serial.py" 2^>nul`) do set "NEXUS_PORT=%%P"

if not defined NEXUS_PORT (
  echo [ERROR] GOOUUU ESP32-S3 serial port was not detected.
  echo Reconnect the USB data cable, then run this file again.
  goto :failed
)

echo [NeXus] Monitoring %NEXUS_PORT% at 115200 baud. Press Ctrl+C or close this window to stop.
pio device monitor --port %NEXUS_PORT% --baud 115200
exit /b %errorlevel%

:failed
pause
exit /b 1
