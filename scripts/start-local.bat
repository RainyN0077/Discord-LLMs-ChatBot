@echo off
setlocal EnableExtensions

cd /d "%~dp0\.."
set "ROOT_DIR=%CD%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"
set "VENV_DIR=%BACKEND_DIR%\.venv"

echo [1/6] Checking Python...
set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    ) else (
        where python3 >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=python3"
        )
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python not found. Install Python 3.10+ and retry.
    exit /b 1
)

echo [2/6] Creating virtual environment if needed...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
)

echo [3/6] Installing backend dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip/setuptools/wheel.
    exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install backend requirements.
    exit /b 1
)

echo [4/6] Preparing frontend dependencies...
where npm >nul 2>&1
if not errorlevel 1 (
    pushd "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] npm install failed.
        exit /b 1
    )
    popd
) else (
    echo [WARN] npm not found, frontend will not start.
)

echo [5/6] Starting backend on http://localhost:8093 ...
start "Backend (Uvicorn)" cmd /k call "%~dp0run-backend-local.bat" "%BACKEND_DIR%" "%VENV_DIR%"

echo [6/6] Starting frontend on http://localhost:8094 ...
where npm >nul 2>&1
if not errorlevel 1 (
    start "Frontend (Vite)" cmd /k "cd /d ""%FRONTEND_DIR%"" && set VITE_API_PROXY_TARGET=http://localhost:8093 && npm run dev -- --host 0.0.0.0 --port 8094"
) else (
    echo [WARN] Skipped frontend startup because npm is unavailable.
)

echo Startup scripts launched.
echo Backend:  http://localhost:8093
echo Frontend: http://localhost:8094
exit /b 0
