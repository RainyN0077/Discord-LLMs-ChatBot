$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"

Write-Host "[1/3] Locating local dev processes..."

$targets = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -and (
        $_.CommandLine -like "*uvicorn app.main:app*" -or
        $_.CommandLine -like "*uvicorn app.portrait_service:app*"
    ) -and (
        $_.CommandLine -like "*$backendDir*" -or
        $_.CommandLine -like "*Discord-LLMs-ChatBot*"
    )
}

$frontTargets = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "node.exe" -and $_.CommandLine -and (
        $_.CommandLine -like "*vite*" -or
        $_.CommandLine -like "*npm run dev*"
    ) -and (
        $_.CommandLine -like "*--port 8094*" -or
        $_.CommandLine -like "*$frontendDir*" -or
        $_.CommandLine -like "*Discord-LLMs-ChatBot*"
    )
}

$allTargets = @($targets + $frontTargets | Sort-Object ProcessId -Unique)

if (-not $allTargets -or $allTargets.Count -eq 0) {
    Write-Host "[2/3] No matching local dev process found."
    Write-Host "[3/3] Done."
    exit 0
}

Write-Host "[2/3] Stopping $($allTargets.Count) process(es)..."
foreach ($p in $allTargets) {
    try {
        Stop-Process -Id $p.ProcessId -Force
        Write-Host ("  - stopped PID {0} ({1})" -f $p.ProcessId, $p.Name)
    } catch {
        Write-Warning ("  - failed PID {0}: {1}" -f $p.ProcessId, $_.Exception.Message)
    }
}

Write-Host "[3/3] Done."
Write-Host "Stopped backend/frontend local dev processes for this project."
