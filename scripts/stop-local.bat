@echo off
setlocal EnableExtensions

cd /d "%~dp0\.."
set "ROOT_DIR=%CD%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

echo [1/3] Locating local dev processes...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$backend='%BACKEND_DIR%'; $frontend='%FRONTEND_DIR%';" ^
  "$targets=Get-CimInstance Win32_Process | Where-Object {" ^
  "($_.Name -eq 'python.exe' -and $_.CommandLine -and (($_.CommandLine -like '*uvicorn app.main:app*') -or ($_.CommandLine -like '*uvicorn app.portrait_service:app*')) -and (($_.CommandLine -like ('*'+$backend+'*')) -or ($_.CommandLine -like '*Discord-LLMs-ChatBot*'))) -or" ^
  "($_.Name -eq 'node.exe' -and $_.CommandLine -and (($_.CommandLine -like '*vite*') -or ($_.CommandLine -like '*npm run dev*')) -and (($_.CommandLine -like '*--port 8094*') -or ($_.CommandLine -like ('*'+$frontend+'*')) -or ($_.CommandLine -like '*Discord-LLMs-ChatBot*')))" ^
  "} | Sort-Object ProcessId -Unique;" ^
  "if(-not $targets){ Write-Host '[2/3] No matching local dev process found.'; Write-Host '[3/3] Done.'; exit 0 };" ^
  "Write-Host ('[2/3] Stopping ' + $targets.Count + ' process(es)...');" ^
  "foreach($p in $targets){ try { Stop-Process -Id $p.ProcessId -Force; Write-Host ('  - stopped PID ' + $p.ProcessId + ' (' + $p.Name + ')') } catch { Write-Warning ('  - failed PID ' + $p.ProcessId + ': ' + $_.Exception.Message) } };" ^
  "Write-Host '[3/3] Done.'; Write-Host 'Stopped backend/frontend local dev processes for this project.'"

exit /b %ERRORLEVEL%
