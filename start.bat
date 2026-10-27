@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Python 3.10+ is required: https://www.python.org/downloads/
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -U pip
  ".venv\Scripts\python.exe" -m pip install -e .
)

if not exist "config.yaml" (
  copy /y "config.example.yaml" "config.yaml" >nul
  echo.
  echo Created config.yaml. Fill in course.main_url and cookie_file, then run this again.
  notepad "config.yaml"
  pause
  exit /b 0
)

if not exist "assets\SourceHanSansSC-Normal.otf" (
  echo [2/3] Downloading reference font...
  ".venv\Scripts\python.exe" scripts\fetch_reference_font.py
)

echo [3/3] Discovering sections...
".venv\Scripts\python.exe" -m webquiz discover -c config.yaml
echo.
echo Done. See out\discover.json and out\html\.
pause
