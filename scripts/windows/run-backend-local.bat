@echo off
setlocal EnableExtensions

set "BACKEND_DIR=%~1"
set "VENV_DIR=%~2"

if not defined BACKEND_DIR (
    echo [ERROR] Missing BACKEND_DIR argument.
    exit /b 1
)
if not defined VENV_DIR (
    echo [ERROR] Missing VENV_DIR argument.
    exit /b 1
)

cd /d "%BACKEND_DIR%" || (
    echo [ERROR] Failed to enter backend directory: "%BACKEND_DIR%"
    exit /b 1
)

set REDIS_HOST=localhost
set REDIS_PORT=6379
set FAIL_ON_REDIS_ERROR=false

"%VENV_DIR%\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8093 --reload
exit /b %ERRORLEVEL%
