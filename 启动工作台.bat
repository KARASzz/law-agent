@echo off
setlocal

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "WORKBENCH_URL=http://%HOST%:%PORT%/workbench"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

echo [Law Agent] Project: %CD%
echo [Law Agent] Python: %PYTHON_CMD%

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [Law Agent] Port %PORT% is already listening.
    echo [Law Agent] Opening %WORKBENCH_URL%
    start "" "%WORKBENCH_URL%"
    pause
    exit /b 0
)

"%PYTHON_CMD%" -c "import fastapi, uvicorn" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [Law Agent] Missing FastAPI or uvicorn.
    echo [Law Agent] Please run:
    echo     "%PYTHON_CMD%" -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [Law Agent] Opening %WORKBENCH_URL%
start "" "%WORKBENCH_URL%"

echo [Law Agent] Starting API service. Press Ctrl+C to stop.
"%PYTHON_CMD%" -m law_agent.main api

pause
