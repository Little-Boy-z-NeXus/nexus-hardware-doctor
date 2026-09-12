@echo off
setlocal EnableExtensions
title NeXus N03 Physical Acceptance
cd /d "%~dp0"

where pio >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PlatformIO was not found. Double-click nexus-setup.cmd first.
  goto :failed
)

echo ============================================================
echo  NeXus N03 - supervised physical command acceptance
echo ============================================================
echo This uploads command-test firmware and briefly runs the motor at 30%% PWM.
echo Secure the motor and keep the 12 V quick disconnect within reach.
choice /C YN /N /M "Hardware is secured and ready? [Y/N]: "
if errorlevel 2 exit /b 2

pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8-command-test --target upload --upload-port COM8
if errorlevel 1 goto :failed

python scripts\nexus_n03_hardware_acceptance.py --port COM8 --confirm-hardware
if errorlevel 1 goto :failed

echo.
echo [SUCCESS] N03 physical acceptance passed.
echo Evidence is stored under artifacts\N03.
pause
exit /b 0

:failed
echo.
echo [NOT READY] N03 is not complete. Read the error above.
echo Turn off the 12 V motor supply if the motor is not already stopped.
pause
exit /b 1
