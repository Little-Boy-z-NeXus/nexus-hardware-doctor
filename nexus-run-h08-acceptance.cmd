@echo off
setlocal EnableExtensions
chcp 65001 >nul
title NeXus H08 Release Acceptance
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

echo [NEXUS][H08] Chạy unit test cho release gate...
"backend\.venv\Scripts\python.exe" -m pytest backend\tests\test_h08_release_acceptance.py backend\tests\test_diagnosis_api.py -q
if errorlevel 1 goto :failed

docker info >nul 2>&1
if errorlevel 1 (
  echo [NEXUS][H08][FAIL] Docker Desktop chưa chạy. Hãy mở Docker Desktop rồi chạy lại file này.
  goto :failed
)

echo [NEXUS][H08] Build image sạch, không dùng API key hoặc COM port...
docker rm --force nexus-h08-acceptance >nul 2>&1
docker build --tag nexus-h08-acceptance:local .
if errorlevel 1 goto :failed
docker run --detach --name nexus-h08-acceptance --publish 127.0.0.1:18008:8000 --env NEXUS_ENABLE_LIVE_MODEL=false --env NEXUS_NEBIUS_BASE_URL= --env NEXUS_NEBIUS_API_KEY= --env NEXUS_NVIDIA_MODEL= nexus-h08-acceptance:local >nul
if errorlevel 1 goto :failed

echo [NEXUS][H08] Kiểm tra startup, telemetry, offline fallback và lỗi model 503 có kiểm soát...
"backend\.venv\Scripts\python.exe" scripts\nexus_h08_release_acceptance.py http://127.0.0.1:18008
set "NEXUS_H08_RESULT=%ERRORLEVEL%"
docker logs nexus-h08-acceptance
docker rm --force nexus-h08-acceptance >nul 2>&1
if not "%NEXUS_H08_RESULT%"=="0" goto :failed

echo [NEXUS][H08][PASS] Evidence: artifacts\H08\nexus-h08-release-acceptance.json
pause
exit /b 0

:failed
docker rm --force nexus-h08-acceptance >nul 2>&1
echo [NEXUS][H08][FAIL] Release gate chưa đạt. Xem thông báo ngay phía trên.
pause
exit /b 1
