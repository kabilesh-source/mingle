@echo off
cd /d "%~dp0"
where py
where python
py -3 --version
python --version
netstat -ano | findstr :8765
pause
