@echo off
REM Stop the one WorkBuddy application process.
REM KEEP THIS FILE ASCII-ONLY.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service-tools.ps1" stop
endlocal
