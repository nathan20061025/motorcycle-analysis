@echo off
rem Double-click to start the app (needs the one-time setup from HOW_TO_RUN.txt).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Do the one-time setup in HOW_TO_RUN.txt first.
  pause
  exit /b 1
)
.venv\Scripts\python run_app.py
pause
