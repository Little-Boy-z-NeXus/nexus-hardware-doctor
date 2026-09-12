@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus Nebius Setup
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [NEXUS][CONFIG] Đang cài dependency lần đầu...
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

"backend\.venv\Scripts\python.exe" "scripts\nexus_configure_nebius.py" --prompt-for-key
if errorlevel 1 goto :failed

echo [NEXUS][CONFIG][READY] Đã lưu cấu hình cục bộ. Key không được in hoặc đưa lên Git.
pause
exit /b 0

:failed
echo [NEXUS][CONFIG][FAIL] Không thể hoàn tất cấu hình. Key chưa được lưu nếu đầu vào không hợp lệ.
pause
exit /b 1
