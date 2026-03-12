@echo off
setlocal EnableExtensions

cd /d "%~dp0\..\.."
set "STOP_SCRIPT=%~dp0stop-local.ps1"

if not exist "%STOP_SCRIPT%" (
    echo [ERROR] Missing script: "%STOP_SCRIPT%"
    exit /b 1
)

echo Running stop script...
powershell -NoProfile -ExecutionPolicy Bypass -File "%STOP_SCRIPT%"

exit /b %ERRORLEVEL%
