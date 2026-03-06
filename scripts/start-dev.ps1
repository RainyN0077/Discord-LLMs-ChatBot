param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'

function Write-Step($message) {
    Write-Host "[QuickStart] $message" -ForegroundColor Cyan
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Step "Repository: $repoRoot"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not installed or not in PATH."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is not installed or not in PATH."
}

if (-not (Test-Path $venvPython)) {
    Write-Step "Creating backend virtual environment..."
    & python -m venv $venvDir
}

Write-Step "Installing backend dependencies..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")

$backendLauncher = @"
`$Host.UI.RawUI.WindowTitle = 'Discord-LLMs-ChatBot Backend'
Set-Location '$repoRoot'
& '$venvPython' -m uvicorn backend.app.main:app --host 0.0.0.0 --port $BackendPort --reload
"@

$frontendLauncher = @"
`$Host.UI.RawUI.WindowTitle = 'Discord-LLMs-ChatBot Frontend'
Set-Location '$frontendDir'
if (-not (Test-Path 'node_modules')) {
    npm install
}
npm run dev -- --host 0.0.0.0 --port $FrontendPort
"@

Write-Step "Starting backend in a new PowerShell window..."
Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $backendLauncher
)

Write-Step "Starting frontend in a new PowerShell window..."
Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $frontendLauncher
)

$frontendUrl = "http://localhost:$FrontendPort"
Start-Sleep -Seconds 2
Write-Step "Opening frontend: $frontendUrl"
Start-Process $frontendUrl

Write-Host "`nDone! Use the opened frontend page to manage the bot." -ForegroundColor Green
Write-Host "Frontend URL: $frontendUrl"
Write-Host "Backend URL:  http://localhost:$BackendPort"
