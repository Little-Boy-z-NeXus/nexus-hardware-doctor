@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus U05 Hardware Baseline - 30 minutes
cd /d "%~dp0"

echo ============================================================
echo  NeXus U05 - supervised 30-minute hardware baseline
echo ============================================================
echo.
echo This test will run the JGB37-520 at 30%% PWM for 30 minutes.
echo Keep one hand near the physical 12V disconnect at all times.
echo The motor starts only after you answer every safety question.
echo.

call "%~dp0nexus-stop-app.cmd"
if errorlevel 1 goto :failed

where pio >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PlatformIO was not found. Run nexus-setup.cmd first.
  goto :failed
)

if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend Python environment is missing. Run nexus-setup.cmd first.
  goto :failed
)

echo [NeXus] Uploading supervised baseline firmware. Motor remains OFF after upload.
pio run --project-dir "%~dp0firmware" --environment nexus-goouuu-esp32-s3-n16r8-baseline --target upload
if errorlevel 1 goto :restore

"%~dp0backend\.venv\Scripts\python.exe" "%~dp0scripts\nexus_hardware_baseline.py" --minutes 30 --pwm 30
set "NEXUS_BASELINE_RESULT=%ERRORLEVEL%"

:restore
echo.
echo [NeXus] Restoring normal safe firmware with USB motor commands disabled...
pio run --project-dir "%~dp0firmware" --environment nexus-goouuu-esp32-s3-n16r8 --target upload
if errorlevel 1 (
  echo [CRITICAL] Normal firmware restore failed.
  echo Disconnect 12V motor power before resetting or unplugging USB.
  goto :failed
)

start "" "%~dp0nexus-start-app.cmd"
if not defined NEXUS_BASELINE_RESULT set "NEXUS_BASELINE_RESULT=1"
if not "%NEXUS_BASELINE_RESULT%"=="0" goto :failed

echo [SUCCESS] U05 electrical and physical checklist passed.
echo Evidence is stored under artifacts\U05.
pause
exit /b 0

:failed
echo.
echo [NOT READY] U05 is not complete. Read the error above and do not bypass it.
pause
exit /b 1
