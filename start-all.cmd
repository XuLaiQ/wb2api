@echo off
REM WorkBuddy unified application. One command starts the panel and its Go gateway.
REM KEEP THIS FILE ASCII-ONLY.
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%config.json" (
  copy /y "%ROOT%config.example.json" "%ROOT%config.json" >nul
  echo Created config.json from config.example.json. Set api_key before serving traffic.
)
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo [ERROR] Missing "%ROOT%.venv\Scripts\python.exe"
  echo         Create it with: python -m venv .venv
  echo         Then install: .venv\Scripts\python -m pip install -r server\requirements.txt
  exit /b 1
)
echo Starting WorkBuddy on http://127.0.0.1:7864 ...
start "WorkBuddy" /D "%ROOT%" cmd /k "%ROOT%start.cmd"
echo The single application window owns both the FastAPI panel and Go gateway.
echo Stop it with stop-all.cmd or Ctrl+C in that window.
endlocal
