@echo off
setlocal EnableExtensions
title NeXus N05 Fault Acceptance
cd /d "%~dp0"

echo ============================================================
echo  NeXus N05 - supervised fault profiles, 5/5 each
echo ============================================================
echo Secure the motor and keep the 12 V quick disconnect within reach.
choice /C YN /N /M "Hardware is secured and OUT2 is currently connected? [Y/N]: "
if errorlevel 2 exit /b 2

pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8-fault-test --target upload --upload-port COM8
if errorlevel 1 goto :failed

backend\.venv\Scripts\python.exe scripts\nexus_n05_fault_acceptance.py --port COM8 --confirm-hardware --software-only
if errorlevel 1 goto :failed

echo.
echo [MANUAL STEP] Turn OFF 12 V. Disconnect only motor wire OUT2/M-.
echo Keep USB, INA226 and common GND connected. Then turn 12 V ON.
pause
backend\.venv\Scripts\python.exe scripts\nexus_n05_fault_acceptance.py --port COM8 --confirm-hardware --manual-out2-confirmed
if errorlevel 1 goto :failed

echo.
echo [RESTORE] Turn OFF 12 V, reconnect OUT2/M-, then turn 12 V ON.
pause
backend\.venv\Scripts\python.exe scripts\nexus_n05_fault_acceptance.py --port COM8 --confirm-hardware --verify-restored
if errorlevel 1 goto :failed

echo.
echo [SUCCESS] All N05 profiles reproduced 5/5 and baseline was restored.
echo Evidence is stored under artifacts\N05.
pause
exit /b 0

:failed
echo.
echo [NOT READY] N05 is not complete. Turn OFF 12 V and inspect the error.
pause
exit /b 1
