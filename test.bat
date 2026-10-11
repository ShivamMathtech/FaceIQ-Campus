@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install.bat first. & exit /b 1)
.venv\Scripts\python.exe -m pytest backend\tests -q
if errorlevel 1 exit /b 1
pushd frontend
call npm test
if errorlevel 1 (popd & exit /b 1)
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd
