@echo off
cd /d "%~dp0"
if not exist venv\Scripts\pythonw.exe (
  echo No venv. Run: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
start "" venv\Scripts\pythonw.exe l2gui.py
