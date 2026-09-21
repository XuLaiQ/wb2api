@echo off
REM WorkBuddy - stop both services on Windows (native).
REM
REM The upstream gateway runs hidden and is stopped by PID file.
REM The manager panel runs in its own console window - this script cannot close
REM it reliably, so it tells you to do it. (Trying to kill it by name would also
REM risk hitting an unrelated python.exe.)
REM
REM KEEP THIS FILE ASCII-ONLY (see start-all.cmd for why).

setlocal
set "ROOT=%~dp0"
set "UP=%ROOT%upstream"

echo [1/2] Stopping upstream workbuddy2api ...
if exist "%UP%\stop-workbuddy2api.cmd" (
  call "%UP%\stop-workbuddy2api.cmd"
) else (
  echo   [WARN] "%UP%\stop-workbuddy2api.cmd" not found - stop it manually.
)

echo [2/2] Manager panel ...
echo   The panel runs in its own window. Close that window or press Ctrl+C
echo   in it to stop the panel.

echo.
echo Done.
endlocal
