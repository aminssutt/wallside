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

  function New-PythonRuntime {
    param(
      [string]$ExePath,
      [string[]]$PrefixArgs = @()
    )

    return @{
      ExePath = $ExePath
      PrefixArgs = $PrefixArgs
    }
  }

  function Test-PythonExecutable {
    param(
      [string]$ExePath
    )

    if (-not $ExePath) {
      return $false
    }

    try {
      & $ExePath -c "import sys; print(sys.executable)" *> $null
      return ($LASTEXITCODE -eq 0)
    } catch {
      return $false
    }
  }

  function Test-PyLauncher {
    param(
      [string]$ExePath
    )

    if (-not $ExePath) {
      return $false
    }

    try {
      & $ExePath -3 -c "import sys; print(sys.executable)" *> $null
      return ($LASTEXITCODE -eq 0)
    } catch {
      return $false
    }
  }

  $venvPython = Join-Path $BackendPath ".venv\\Scripts\\python.exe"
  if ((Test-Path $venvPython) -and (Test-PythonExecutable -ExePath $venvPython)) {
    return (New-PythonRuntime -ExePath $venvPython)
  }

  if (Test-Path $venvPython) {
    Write-Host "Warning: backend/.venv detected but invalid, falling back to system Python."
  }

  $pythonCandidates = @()

  foreach ($cmdName in @("python", "python3")) {
    $cmd = Get-Command $cmdName -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
      $pythonCandidates += $cmd.Source
    }
  }

  try {
    $wherePython = where.exe python 2>$null
    if ($wherePython) {
      $pythonCandidates += $wherePython
    }
  } catch {}

  $pythonCandidates = $pythonCandidates |
    Where-Object { $_ -and (Test-Path $_) } |
    Select-Object -Unique

  foreach ($candidate in $pythonCandidates) {
    if (Test-PythonExecutable -ExePath $candidate) {
      return (New-PythonRuntime -ExePath $candidate)
    }
  }

  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd -and (Test-PyLauncher -ExePath $pyCmd.Source)) {
    return (New-PythonRuntime -ExePath $pyCmd.Source -PrefixArgs @("-3"))
  }

  throw "Python not found or not runnable. Install Python or recreate backend/.venv."
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

$pythonRuntime = Resolve-PythonExe -BackendPath $backendDir
$pythonExe = $pythonRuntime.ExePath
$pythonPrefixArgs = @($pythonRuntime.PrefixArgs)
$backendArgs = @()
if ($pythonPrefixArgs.Count -gt 0) {
  $backendArgs += $pythonPrefixArgs
}
$backendArgs += "api.py"

Start-Process `
  -FilePath $pythonExe `
  -ArgumentList $backendArgs `
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
