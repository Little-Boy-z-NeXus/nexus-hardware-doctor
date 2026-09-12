@echo off
setlocal EnableExtensions
title NeXus Backend - http://127.0.0.1:8000
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  set "NEXUS_NO_PAUSE=1"
  call "%~dp0nexus-setup.cmd"
  if errorlevel 1 goto :failed
)

set "NEXUS_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
"%NEXUS_PYTHON%" -c "import nexus_backend, serial, uvicorn" >nul 2>&1
if errorlevel 1 (
  echo [NeXus] Backend dependencies are missing; installing them now...
  "%NEXUS_PYTHON%" -m pip install -e ".\backend[dev]"
  if errorlevel 1 goto :failed
)

echo [NeXus] Backend: http://127.0.0.1:8000
echo [NeXus] API docs: http://127.0.0.1:8000/docs
set "NEXUS_ENV_FILE_OPTION="
if exist ".env" set "NEXUS_ENV_FILE_OPTION=--env-file .env"
"%NEXUS_PYTHON%" -m uvicorn nexus_backend.app:app --reload --reload-dir "%CD%\backend\src" --host 127.0.0.1 --port 8000 %NEXUS_ENV_FILE_OPTION%
exit /b %errorlevel%

:failed
echo [ERROR] Backend could not start.
pause
exit /b 1
