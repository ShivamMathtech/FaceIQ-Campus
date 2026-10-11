@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python launcher missing. Install Python 3.12 x64 with py launcher. & exit /b 1)
where node >nul 2>nul
if errorlevel 1 (echo Node.js missing. Install Node.js 22 LTS or newer. & exit /b 1)
node -e "if(Number(process.versions.node.split('.')[0])<22)process.exit(1)"
if errorlevel 1 (echo Node.js 22 or newer is required. & exit /b 1)
py -3.12 -c "import sys; assert sys.maxsize > 2**32"
if errorlevel 1 (echo Python 3.12 x64 is required. & exit /b 1)
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto :fail
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :fail
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto :fail
.venv\Scripts\python.exe scripts\configure.py
if errorlevel 1 goto :fail
.venv\Scripts\python.exe scripts\initialize_database.py
if errorlevel 1 goto :fail
pushd frontend
call npm ci --no-fund
if errorlevel 1 (popd & goto :fail)
call npm run build
if errorlevel 1 (popd & goto :fail)
popd
echo.
echo Dependencies, configuration and database are ready.
echo Next: .venv\Scripts\python.exe scripts\create_admin.py
echo Optional models: .venv\Scripts\python.exe scripts\download_or_configure_model.py
echo Launch: run_all.bat
exit /b 0
:fail
echo Installation failed. Read the error above. Re-running preserves existing data and configuration.
exit /b 1
