@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus H06 Acceptance
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

echo [NEXUS][H06] Kiểm tra policy default-deny và five-cycle physical verification...
"backend\.venv\Scripts\python.exe" -m pytest backend\tests\test_policy.py backend\tests\test_orchestrator.py backend\tests\test_n06_auto_heal_acceptance.py backend\tests\test_h06_acceptance.py -q
if errorlevel 1 goto :failed
"backend\.venv\Scripts\python.exe" scripts\nexus_h06_acceptance.py
if errorlevel 1 goto :failed

echo [NEXUS][H06][PASS] Evidence: artifacts\H06\nexus-h06-acceptance.json
pause
exit /b 0

:failed
echo [NEXUS][H06][FAIL] Cần policy tests xanh và N06 Auto Heal physical PASS 5/5.
pause
exit /b 1
