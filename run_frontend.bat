@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install.bat first. & exit /b 1)
.venv\Scripts\python.exe scripts\check_port.py 5173
if errorlevel 1 exit /b 1
echo FaceIQ Campus: http://127.0.0.1:5173
echo Logs appear in this window. Press Ctrl+C for clean shutdown.
cd frontend
call npm run dev
