@echo off
setlocal
cd /d "%~dp0"
title NeXus Hardware Profile Validator

if not exist "backend\.venv\Scripts\python.exe" (
  echo [NeXus] Backend environment is missing. Running setup first...
  call nexus-setup.cmd --no-pause
  if errorlevel 1 goto :fail
)

set "NEXUS_NO_PAUSE=0"
if /i "%~1"=="--no-pause" (
  set "NEXUS_NO_PAUSE=1"
  set "NEXUS_PROFILE="
) else (
  set "NEXUS_PROFILE=%~1"
)
if /i "%~2"=="--no-pause" set "NEXUS_NO_PAUSE=1"
if "%NEXUS_PROFILE%"=="" set "NEXUS_PROFILE=nexus-hardware\profiles\nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1.json"

echo [NeXus] Validating %NEXUS_PROFILE%
"backend\.venv\Scripts\python.exe" -m nexus_backend.hardware_profile "%NEXUS_PROFILE%" --json
if errorlevel 1 goto :fail

echo.
echo [NeXus] Profile is valid and ready for firmware/backend use.
if "%NEXUS_NO_PAUSE%"=="0" pause
exit /b 0

:fail
echo.
echo [NeXus] Hardware profile validation failed.
if "%NEXUS_NO_PAUSE%"=="0" pause
exit /b 1
