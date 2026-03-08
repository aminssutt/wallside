$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"

$backendLog = Join-Path $backendDir "backend-dev.log"
$backendErrLog = Join-Path $backendDir "backend-dev.err.log"
$frontendLog = Join-Path $frontendDir "frontend-dev.log"
$frontendErrLog = Join-Path $frontendDir "frontend-dev.err.log"

function Stop-PortProcess {
  param(
    [int]$Port
  )

  $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $listeners) {
    return
  }

  $pids = $listeners.OwningProcess | Select-Object -Unique
  foreach ($procId in $pids) {
    try {
      Stop-Process -Id $procId -Force -ErrorAction Stop
      Write-Host "Stopped process on port $Port (PID: $procId)"
    } catch {
      Write-Host "Could not stop PID $procId on port $Port"
    }
  }
}

function Resolve-PythonExe {
  param(
    [string]$BackendPath
  )

  $venvPython = Join-Path $BackendPath ".venv\\Scripts\\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) {
    return $pythonCmd.Source
  }

  throw "Python not found. Install Python or create backend/.venv first."
}

if (-not (Test-Path $backendDir)) {
  throw "backend directory not found: $backendDir"
}

if (-not (Test-Path $frontendDir)) {
  throw "frontend directory not found: $frontendDir"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm not found in PATH."
}

Stop-PortProcess -Port 5002
Stop-PortProcess -Port 5173

$pythonExe = Resolve-PythonExe -BackendPath $backendDir

Start-Process `
  -FilePath $pythonExe `
  -ArgumentList "api.py" `
  -WorkingDirectory $backendDir `
  -RedirectStandardOutput $backendLog `
  -RedirectStandardError $backendErrLog | Out-Null

Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173" `
  -WorkingDirectory $frontendDir `
  -RedirectStandardOutput $frontendLog `
  -RedirectStandardError $frontendErrLog | Out-Null

Start-Sleep -Seconds 2

try {
  $health = Invoke-RestMethod -Uri "http://localhost:5002/api/health" -TimeoutSec 10
  Write-Host "Backend: OK ($($health.status)) -> http://localhost:5002"
} catch {
  Write-Host "Backend: not reachable yet. Check $backendErrLog"
}

try {
  $null = curl.exe -I "http://localhost:5173" 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Frontend: OK -> http://localhost:5173"
  } else {
    Write-Host "Frontend: not reachable yet. Check $frontendErrLog"
  }
} catch {
  Write-Host "Frontend: not reachable yet. Check $frontendErrLog"
}

Write-Host ""
Write-Host "Logs:"
Write-Host "  backend:  $backendLog"
Write-Host "  frontend: $frontendLog"
