@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo Building default-safe firmware and recovery bundle...
pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8
if errorlevel 1 goto :failed
python scripts\nexus_n08_prepare_recovery_kit.py
if errorlevel 1 goto :failed
echo [NEXUS][PASS] Copy artifacts\N08\recovery-kit to the labelled backup USB drive.
pause
exit /b 0

:failed
echo [NEXUS][FAIL] Recovery kit was not created.
pause
exit /b 1
