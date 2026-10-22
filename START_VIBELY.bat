@echo off
setlocal
cd /d "%~dp0"
title VIBELY - Local App
set "PYTHON_EXE="
where py >nul 2>&1
if not errorlevel 1 (set "PYTHON_EXE=py -3")
if not defined PYTHON_EXE (
  where python >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
  echo ERROR: Python 3 is not installed or not in PATH.
  echo Install Python from python.org and check "Add Python to PATH".
  pause
  exit /b 1
)
echo Starting VIBELY... keep this window open.
echo Open http://localhost:8765 in your browser.
start "" "http://localhost:8765"
%PYTHON_EXE% server.py
if errorlevel 1 (
 echo.
 echo App failed to start. Read the error above.
 echo If port 8765 is busy, close the other app using that port.
)
pause
