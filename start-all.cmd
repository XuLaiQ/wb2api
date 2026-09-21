@echo off
REM WorkBuddy - start both services on Windows (native, no Docker).
REM
REM   upstream workbuddy2api  ->  127.0.0.1:7863   (OpenAI-compatible gateway)
REM   manager panel           ->  127.0.0.1:7864   (web panel + outbound gateway)
REM
REM KEEP THIS FILE ASCII-ONLY. cmd.exe parses batch files with the system ANSI
REM codepage (936/GBK on Chinese Windows); UTF-8 comments get mangled and the
REM mangled fragments are executed as commands, so the user sees spurious
REM "not recognized as an internal or external command" errors.
REM
REM Prefer Docker? Use:  docker compose up -d --build   (from this directory)

setlocal
set "ROOT=%~dp0"
set "UP=%ROOT%upstream"
set "MG=%ROOT%manager"

if not exist "%UP%\wb2api.exe" (
  echo [ERROR] Missing "%UP%\wb2api.exe"
  echo         Build it once:  cd /d "%UP%" ^&^& go build -o wb2api.exe ./cmd/server
  exit /b 1
)
if not exist "%UP%\config.json" (
  echo [ERROR] Missing "%UP%\config.json"
  echo         Copy config.example.json to config.json, then set api_key and admin.enabled.
  exit /b 1
)
if not exist "%MG%\.venv\Scripts\python.exe" (
  echo [ERROR] Missing the manager virtualenv "%MG%\.venv"
  echo         Create it once:
  echo           cd /d "%MG%"
  echo           python -m venv .venv
  echo           .venv\Scripts\python -m pip install -r server\requirements.txt
  exit /b 1
)

echo [1/2] Starting upstream workbuddy2api on 127.0.0.1:7863 ...
call "%UP%\start-workbuddy2api.cmd"
if errorlevel 1 (
  echo [ERROR] Upstream failed to start. See "%UP%\data\server.err.log"
  exit /b 1
)

echo [2/2] Starting manager panel on 127.0.0.1:7864 ...
REM Runs in its own window in the foreground - closing that window stops the panel.
start "WorkBuddy Manager" /D "%MG%" cmd /k "%MG%\start.cmd"

echo.
echo   upstream : http://127.0.0.1:7863
echo   panel    : http://127.0.0.1:7864
echo.
echo   First run without WB_ADMIN_PASSWORD prints a random admin password
echo   in the manager window - copy it before it scrolls away.
echo   Stop everything with: stop-all.cmd
echo.
endlocal
