@echo off
setlocal EnableExtensions
title NeXus Firmware Upload
cd /d "%~dp0"

where pio >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PlatformIO was not found. Double-click nexus-setup.cmd first.
  goto :failed
)

echo [NeXus] Uploading MVP v1 firmware: GOOUUU ESP32-S3 + INA226 R100 + L298N + one JGB37-520...
echo [NeXus] Use the USB connector that creates the CH340/CH343 COM port.
pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-ina226-r100-mvp-v1-uart --target upload
if errorlevel 1 goto :failed

echo.
echo [SUCCESS] MVP v1 INA226 R100 firmware was uploaded and verified.
echo [NEXT] Start the app; verify sensor=ina226-r100, voltage/current and encoder A/B before running the motor.
if /I not "%~1"=="--no-pause" pause
exit /b 0

:failed
echo.
echo [ERROR] Firmware upload failed. Close Serial Monitor, reconnect USB, and try again.
if /I not "%~1"=="--no-pause" pause
exit /b 1
