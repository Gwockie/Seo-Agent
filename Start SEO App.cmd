@echo off
cd /d "%~dp0"
if not exist ".venv-mvp\Scripts\python.exe" (
  echo The app environment is missing. Ask the agent to finish local setup.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8502 on this computer.
echo Keep this window open while using the app. Close it to stop the app.
".venv-mvp\Scripts\python.exe" -m seo_agent app --port 8502
if errorlevel 1 pause
