@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus Submission Gate
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

set "NEXUS_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
echo [NEXUS][1/6] Repository, contracts, and Hardware-as-Code...
"%NEXUS_PYTHON%" scripts\validate_repo.py
if errorlevel 1 goto :failed
"%NEXUS_PYTHON%" scripts\validate_contracts.py
if errorlevel 1 goto :failed
"%NEXUS_PYTHON%" -m nexus_backend.hardware_profile
if errorlevel 1 goto :failed

echo [NEXUS][2/6] Backend lint and unit tests...
"%NEXUS_PYTHON%" -m ruff check backend scripts
if errorlevel 1 goto :failed
"%NEXUS_PYTHON%" -m pytest backend\tests -q
if errorlevel 1 goto :failed

echo [NEXUS][3/6] Frontend lint, unit tests, typecheck, and production build...
call npm --prefix frontend run check
if errorlevel 1 goto :failed

echo [NEXUS][4/6] Final three-wheel PS2 firmware build...
pio run --project-dir firmware --environment nexus-esp32-s3-devkitc-3wheel-ps2
if errorlevel 1 goto :failed

echo [NEXUS][5/6] Five consecutive offline golden paths...
if not exist "artifacts\submission" mkdir "artifacts\submission"
"%NEXUS_PYTHON%" -m nexus_backend.evaluation --repetitions 5 --output artifacts\submission\offline-evaluation.json
if errorlevel 1 goto :failed

echo [NEXUS][6/6] Submission files and tracked-secret scan...
"%NEXUS_PYTHON%" scripts\nexus_submission_readiness.py
if errorlevel 1 goto :failed

echo.
echo [NEXUS][PASS] Automated submission gate passed.
echo [NEXUS][NEXT] Complete the human gates in docs\submission\release-checklist.md.
echo [NEXUS][REPORT] artifacts\submission\readiness.json
pause
exit /b 0

:failed
echo.
echo [NEXUS][FAIL] Submission gate stopped at the failing step above.
pause
exit /b 1
