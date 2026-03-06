@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"
if errorlevel 1 (
  echo.
  echo Failed to start project. Please check the error message above.
  pause
)
endlocal
