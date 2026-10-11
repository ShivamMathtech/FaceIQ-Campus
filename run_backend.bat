@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install.bat first. & exit /b 1)
.venv\Scripts\python.exe scripts\check_port.py 8000
if errorlevel 1 exit /b 1
echo Backend: http://127.0.0.1:8000/api/health
echo API docs: http://127.0.0.1:8000/docs
echo Logs appear in this window. Press Ctrl+C for clean shutdown.
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 65536
