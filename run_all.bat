@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install.bat first. & exit /b 1)
.venv\Scripts\python.exe scripts\check_port.py 8000
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe scripts\check_port.py 5173
if errorlevel 1 exit /b 1
start "FaceIQ Backend" cmd /k ""%~dp0run_backend.bat""
start "FaceIQ Frontend" cmd /k ""%~dp0run_frontend.bat""
echo Open http://127.0.0.1:5173 after both services report ready.
echo Stop with Ctrl+C in each service window. Do not close an active session without finalizing.
