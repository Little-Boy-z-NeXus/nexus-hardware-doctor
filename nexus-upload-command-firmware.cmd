@echo off
setlocal EnableExtensions
title NeXus N03 Command Firmware Upload
cd /d "%~dp0"

where pio >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PlatformIO was not found. Double-click nexus-setup.cmd first.
  goto :failed
)

echo [WARNING] This supervised build enables bounded motor commands.
echo [CHECK] Secure the motor and keep the 12V quick disconnect within reach.
choice /C YN /N /M "Upload command-test firmware? [Y/N]: "
if errorlevel 2 exit /b 2

pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8-command-test --target upload
if errorlevel 1 goto :failed

echo.
echo [SUCCESS] N03 command-test firmware was uploaded and verified.
echo [NEXT] Close every app/monitor using COM, then use scripts\nexus_device_command.py.
pause
exit /b 0

:failed
echo.
echo [ERROR] Upload failed. Close Serial Monitor, reconnect USB, and try again.
pause
exit /b 1
