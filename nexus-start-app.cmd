@echo off
setlocal EnableExtensions
title NeXus Launcher
cd /d "%~dp0"
set "NEXUS_ROOT=%CD%"

echo [NeXus] Checking existing services...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 1; if ($r.service -eq 'nexus-backend') { exit 0 } } catch {}; exit 1"
if errorlevel 1 (
  echo [NeXus] Starting backend in a separate window...
  start "NeXus Backend" /D "%NEXUS_ROOT%" cmd.exe /c call nexus-start-backend.cmd
) else (
  echo [NeXus] Reusing backend already running on port 8000.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 1; if ($r.StatusCode -eq 200 -and $r.Content -match 'NeXus') { exit 0 } } catch {}; exit 1"
if errorlevel 1 (
  echo [NeXus] Starting frontend in a separate window...
  start "NeXus Frontend" /D "%NEXUS_ROOT%" cmd.exe /c call nexus-start-frontend.cmd
) else (
  echo [NeXus] Reusing frontend already running on port 5173.
)

echo [NeXus] Waiting for the web application...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(30); do { try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 1; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo [WARNING] Frontend did not answer within 30 seconds. Check the NeXus Frontend window.
  pause
  exit /b 1
)

start "" "http://127.0.0.1:5173/hardware"
echo [SUCCESS] NeXus is running. Close the Backend and Frontend windows to stop it.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2"
exit /b 0
