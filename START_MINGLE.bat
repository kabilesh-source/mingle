@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
 start "" "http://localhost:8765"
 py -3 server.py
) else (
 where python >nul 2>nul
 if %errorlevel%==0 (
  start "" "http://localhost:8765"
  python server.py
 ) else (
  echo Python 3 is required. Install it from python.org and run again.
  pause
 )
)
