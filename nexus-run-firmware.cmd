@echo off
setlocal EnableExtensions
title NeXus Firmware - Upload and Monitor
cd /d "%~dp0"

call "%~dp0nexus-upload-firmware.cmd" --no-pause
if errorlevel 1 (
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2"
call "%~dp0nexus-monitor-firmware.cmd"
exit /b %errorlevel%
