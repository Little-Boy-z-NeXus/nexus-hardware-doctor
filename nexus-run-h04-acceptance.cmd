@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus H04 Acceptance
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

echo [NEXUS][H04] Kiểm tra planner, schema và evidence model thật đã khóa...
"backend\.venv\Scripts\python.exe" -m pytest backend\tests\test_diagnosis.py backend\tests\test_provider.py backend\tests\test_h04_acceptance.py -q
if errorlevel 1 goto :failed
"backend\.venv\Scripts\python.exe" scripts\nexus_h04_acceptance.py
if errorlevel 1 goto :failed

echo [NEXUS][H04][PASS] Evidence: artifacts\H04\nexus-h04-acceptance.json
pause
exit /b 0

:failed
echo [NEXUS][H04][FAIL] Xem lỗi phía trên. Không có model call hoặc hardware write mới.
pause
exit /b 1
