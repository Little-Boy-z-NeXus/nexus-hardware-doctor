@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "NEXUS_ROOT=%CD%"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [NEXUS][ERROR] Run nexus-setup.cmd first.
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [NEXUS][ERROR] Run nexus-setup.cmd first.
  pause
  exit /b 1
)

call "%~dp0nexus-stop-app.cmd"
start "NeXus Telemetry Replay" /D "%NEXUS_ROOT%" cmd.exe /c backend\.venv\Scripts\python.exe -m nexus_backend.replay_server
start "NeXus Frontend" /D "%NEXUS_ROOT%" cmd.exe /c call nexus-start-frontend.cmd
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(30); do { try { $b=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' -TimeoutSec 1; $f=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173/hardware' -TimeoutSec 1; if ($b.StatusCode -eq 200 -and $f.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo [NEXUS][ERROR] Replay backend or frontend did not start within 30 seconds.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:5173/hardware"

echo [NEXUS][OK] Replaying sanitized telemetry without using COM or physical hardware.
echo Close both spawned windows or run nexus-stop-app.cmd when finished.
exit /b 0
