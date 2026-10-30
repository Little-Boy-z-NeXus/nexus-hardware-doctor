@echo off
setlocal
cd /d "%~dp0"

set "NEXUS_PORT=%~1"
if not defined NEXUS_PORT set "NEXUS_PORT=COM13"

echo [NeXus] PS2 diagnostic on %NEXUS_PORT%
echo [NeXus] Motor outputs are forced OFF in this build.
echo [NeXus] Keep 12V motor power disconnected while testing.
echo.

pio run --project-dir firmware --environment nexus-ps2-diagnostic --target upload --upload-port %NEXUS_PORT%
if errorlevel 1 (
  echo.
  echo [NeXus] Upload failed. Check the COM port and press BOOT/RESET if requested.
  pause
  exit /b 1
)

echo.
echo [NeXus] Move both sticks and press buttons. Look for [NEXUS][PS2_TEST].
echo [NeXus] Press Ctrl+C to stop the monitor.
pio device monitor --port %NEXUS_PORT% --baud 115200 --filter time

endlocal
