@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus H07 Acceptance
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

echo [NEXUS][H07] Chạy regression một lệnh và đối chiếu model/physical evidence...
"backend\.venv\Scripts\python.exe" -m nexus_backend.evaluation --output artifacts\H07\offline-regression.json
if errorlevel 1 goto :failed
"backend\.venv\Scripts\python.exe" -m pytest backend\tests\test_evaluation.py backend\tests\test_h07_acceptance.py -q
if errorlevel 1 goto :failed
"backend\.venv\Scripts\python.exe" scripts\nexus_h07_acceptance.py
if errorlevel 1 goto :failed

echo [NEXUS][H07][PASS] Evidence: artifacts\H07\nexus-h07-acceptance.json
pause
exit /b 0

:failed
echo [NEXUS][H07][FAIL] Cần live score, golden paths 5/5 và N05/N06 physical evidence.
pause
exit /b 1
