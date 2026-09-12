@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo NeXus N08 - Three-minute recovery drill
echo ============================================================
echo Turn OFF 12 V motor power before touching wiring or USB.
set /p "NEXUS_RECOVERY_OPERATOR=Operator name: "
if "%NEXUS_RECOVERY_OPERATOR%"=="" exit /b 1
call "%~dp0nexus-stop-app.cmd"
if errorlevel 1 exit /b 1
if not exist "backend\.venv\Scripts\python.exe" (
  echo [NEXUS][ERROR] Run nexus-setup.cmd first.
  pause
  exit /b 1
)

"backend\.venv\Scripts\python.exe" scripts\nexus_n08_recovery_drill.py --operator "%NEXUS_RECOVERY_OPERATOR%" --limit-seconds 180
if errorlevel 1 goto :failed
echo [NEXUS][PASS] Safe firmware and INA226 telemetry recovered under three minutes.
echo Start the normal app with nexus-start-app.cmd when ready.
pause
exit /b 0

:failed
echo [NEXUS][FAIL] Keep 12 V motor power OFF and ask Hiếu to review the evidence under artifacts\N08.
pause
exit /b 1
