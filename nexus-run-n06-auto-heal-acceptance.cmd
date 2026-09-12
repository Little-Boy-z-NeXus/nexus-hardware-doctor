@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo NeXus N06 - Physical Auto Heal acceptance (5 cycles)
echo ============================================================
echo This test spins the secured motor briefly at max 30%% PWM.
echo Keep the 12 V emergency disconnect within reach.
choice /C YN /N /M "Motor is secured, wiring is unchanged, and emergency stop is ready? [Y/N]: "
if errorlevel 2 exit /b 1

call "%~dp0nexus-stop-app.cmd"
if errorlevel 1 exit /b 1

if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo [NEXUS][ERROR] Run nexus-setup.cmd first.
  pause
  exit /b 1
)

echo Uploading the supervised fault-test firmware...
pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8-fault-test --target upload
if errorlevel 1 goto :failed

"%~dp0backend\.venv\Scripts\python.exe" "%~dp0scripts\nexus_n06_auto_heal_acceptance.py" --confirm-hardware --cycles 5 --pwm-percent 30 --duration-ms 500
set "NEXUS_TEST_EXIT=%ERRORLEVEL%"

echo Restoring default-safe firmware (physical writes disabled)...
pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8 --target upload
if errorlevel 1 (
  echo [NEXUS][ERROR] Default-safe firmware restore failed. Keep 12 V motor power OFF.
  pause
  exit /b 1
)
if not "%NEXUS_TEST_EXIT%"=="0" goto :failed

echo [NEXUS][PASS] N06 passed 5/5 and the board is back on default-safe firmware.
echo Evidence is under artifacts\N06\.
pause
exit /b 0

:failed
echo [NEXUS][FAIL] N06 did not pass. Motor reset was attempted; keep motor power OFF until reviewed.
pause
exit /b 1
