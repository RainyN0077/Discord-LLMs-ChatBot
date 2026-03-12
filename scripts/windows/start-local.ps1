$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "[1/6] Checking Python..."
$pythonExe = $null
$pythonPrefixArgs = @()
$scoopPython = Join-Path $env:USERPROFILE "scoop\apps\python\current\python.exe"

if (Test-Path $scoopPython) {
    $pythonExe = $scoopPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = "py"
        $pythonPrefixArgs = @("-3")
    }
}

if (-not $pythonExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = "python"
    }
}

if (-not $pythonExe -and (Get-Command python3 -ErrorAction SilentlyContinue)) {
    & python3 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = "python3"
    }
}

if (-not $pythonExe) {
    throw "Python not found. Install Python 3.10+ and retry."
}

Write-Host "[2/6] Creating virtual environment if needed..."
if (-not (Test-Path $venvPython)) {
    & $pythonExe @pythonPrefixArgs -m venv $venvDir
}
if (-not (Test-Path $venvPython)) {
    throw "Failed to create virtual environment at $venvDir"
}

Write-Host "[3/6] Installing backend dependencies..."
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")

Write-Host "[4/6] Preparing frontend dependencies..."
$hasNpm = $null -ne (Get-Command npm -ErrorAction SilentlyContinue)
if ($hasNpm) {
    Push-Location $frontendDir
    try {
        & npm install
    } finally {
        Pop-Location
    }
} else {
    Write-Warning "npm not found, frontend will not start."
}

Write-Host "[5/6] Starting backend on http://localhost:8093 ..."
$backendCommand = @"
Set-Location '$backendDir'
& '$venvPython' -m uvicorn app.main:app --host 0.0.0.0 --port 8093 --reload
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand -WorkingDirectory $backendDir -WindowStyle Normal

Write-Host "[6/6] Starting frontend on http://localhost:8094 ..."
if ($hasNpm) {
    $frontendCommand = @"
Set-Location '$frontendDir'
\$env:VITE_API_PROXY_TARGET = 'http://localhost:8093'
npm run dev -- --host 0.0.0.0 --port 8094
"@
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand -WorkingDirectory $frontendDir -WindowStyle Normal
} else {
    Write-Warning "Skipped frontend startup because npm is unavailable."
}

Write-Host "Startup scripts launched."
Write-Host "Backend:  http://localhost:8093"
Write-Host "Frontend: http://localhost:8094"
