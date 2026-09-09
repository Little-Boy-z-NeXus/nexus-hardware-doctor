@echo off
setlocal EnableExtensions
title NeXus Frontend - http://127.0.0.1:5173
cd /d "%~dp0"

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js and npm were not found in PATH.
  goto :failed
)

if not exist "frontend\node_modules" (
  echo [NeXus] Frontend dependencies are missing; installing them now...
  pushd "frontend"
  if exist "package-lock.json" (
    call npm ci
  ) else (
    call npm install
  )
  if errorlevel 1 (
    popd
    goto :failed
  )
  popd
)

if not exist "frontend\.env.local" copy /Y "frontend\.env.example" "frontend\.env.local" >nul

echo [NeXus] Frontend: http://127.0.0.1:5173
pushd "frontend"
call npm run dev
set "NEXUS_EXIT=%errorlevel%"
popd
exit /b %NEXUS_EXIT%

:failed
echo [ERROR] Frontend could not start.
pause
exit /b 1
