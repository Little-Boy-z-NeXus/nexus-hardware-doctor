@echo off
setlocal EnableExtensions
title NeXus Stop Application
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\nexus-stop-app.ps1"
if errorlevel 1 (
  echo [ERROR] NeXus could not stop every application process.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 1"
exit /b 0
