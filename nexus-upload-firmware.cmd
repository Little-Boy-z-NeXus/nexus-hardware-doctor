@echo off
setlocal EnableExtensions
title NeXus Firmware Upload
cd /d "%~dp0"

where pio >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PlatformIO was not found. Double-click nexus-setup.cmd first.
  goto :failed
)

echo [NeXus] Uploading to GOOUUU Tech ESP32-S3-N16R8 through built-in USB-JTAG...
pio run --project-dir firmware --target upload
if errorlevel 1 goto :failed

echo.
echo [SUCCESS] Firmware was uploaded and verified.
if /I not "%~1"=="--no-pause" pause
exit /b 0

:failed
echo.
echo [ERROR] Firmware upload failed. Close Serial Monitor, reconnect USB, and try again.
if /I not "%~1"=="--no-pause" pause
exit /b 1
