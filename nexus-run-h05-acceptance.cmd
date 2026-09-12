@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus H05 Acceptance
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

echo [NEXUS][H05] Kiểm tra orchestrator, serial integration và N03 evidence thật...
"backend\.venv\Scripts\python.exe" -m pytest backend\tests\test_orchestrator.py backend\tests\test_serial_reads.py backend\tests\test_serial_integration.py backend\tests\test_h05_acceptance.py -q
if errorlevel 1 goto :failed
"backend\.venv\Scripts\python.exe" scripts\nexus_h05_acceptance.py
if errorlevel 1 goto :failed

echo [NEXUS][H05][PASS] Evidence: artifacts\H05\nexus-h05-acceptance.json
pause
exit /b 0

:failed
echo [NEXUS][H05][FAIL] Cần một N03 physical PASS trong artifacts\N03 và toàn bộ test xanh.
pause
exit /b 1
