@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus U07 Vertical Slice
cd /d "%~dp0"
set "NEXUS_ROOT=%CD%"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [NEXUS][U07] Đang cài dependency lần đầu...
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)
if not exist ".env" (
  echo [NEXUS][U07][BLOCKED] Chưa có file .env cục bộ.
  echo Sao chép .env.example thành .env, điền Nebius secret ở máy này và bật các biến U07 theo docs\u07-vertical-slice.md.
  goto :failed
)

call "%~dp0nexus-stop-app.cmd"
if errorlevel 1 goto :failed

start "NeXus Backend U07" /D "%NEXUS_ROOT%" cmd.exe /c call nexus-start-backend.cmd
start "NeXus Frontend U07" /D "%NEXUS_ROOT%" cmd.exe /c call nexus-start-frontend.cmd

echo [NEXUS][U07] Đang chờ backend và frontend...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(40); do { try { $b=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' -TimeoutSec 1; $f=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173/dashboard' -TimeoutSec 1; if ($b.StatusCode -eq 200 -and $f.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo [NEXUS][U07][BLOCKED] Software không khởi động đủ trong 40 giây.
  goto :failed
)

echo [NEXUS][U07] Chạy vertical slice thật 3 lần; không có lệnh ghi motor.
"backend\.venv\Scripts\python.exe" "scripts\nexus_u07_vertical_slice.py" --runs 3
if errorlevel 1 goto :failed

start "" "http://127.0.0.1:5173/dashboard"
echo [NEXUS][U07][PASS] Hoàn thành 3/3. Evidence: artifacts\U07\nexus-u07-vertical-slice.json
echo Giữ hai cửa sổ server mở để quay video nội bộ, hoặc chạy nexus-stop-app.cmd để dừng.
pause
exit /b 0

:failed
echo [NEXUS][U07][FAIL] Xem lỗi phía trên và artifacts\U07\nexus-u07-vertical-slice.json nếu đã được tạo.
pause
exit /b 1
