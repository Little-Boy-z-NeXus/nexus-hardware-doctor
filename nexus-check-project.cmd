@echo off
setlocal EnableExtensions
title NeXus Project Checks
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

set "NEXUS_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
"%NEXUS_PYTHON%" -c "import nexus_backend, pytest" >nul 2>&1
if errorlevel 1 (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)
"%NEXUS_PYTHON%" -m ruff --version >nul 2>&1
if errorlevel 1 (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

echo [NeXus] Validating repository...
"%NEXUS_PYTHON%" scripts\validate_repo.py
if errorlevel 1 goto :failed
"%NEXUS_PYTHON%" scripts\validate_contracts.py
if errorlevel 1 goto :failed
"%NEXUS_PYTHON%" -m nexus_backend.hardware_profile
if errorlevel 1 goto :failed

echo [NeXus] Checking backend...
"%NEXUS_PYTHON%" -m ruff check backend scripts
if errorlevel 1 goto :failed
"%NEXUS_PYTHON%" -m pytest backend\tests -q
if errorlevel 1 goto :failed

echo [NeXus] Checking frontend...
call npm --prefix frontend run check
if errorlevel 1 goto :failed

echo [NeXus] Building firmware...
pio run --project-dir firmware
if errorlevel 1 goto :failed

echo.
echo [SUCCESS] All NeXus project checks passed.
pause
exit /b 0

:failed
echo.
echo [ERROR] A NeXus project check failed. Read the output above.
pause
exit /b 1
