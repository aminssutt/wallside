param(
  [string]$ServerUser = "lakhdar",
  [Parameter(Mandatory = $true)]
  [string]$ServerHost,
  [string]$RemoteDir = "/home/lakhdar/auris-training",
  [string]$ContainerName = "auris-training",
  [string]$ImageName = "auris-training:prod",
  [string]$ApiUrl = "/api"
)

$ErrorActionPreference = "Stop"

if ($RemoteDir -notmatch "auris-training") {
  throw "RemoteDir invalide pour ce projet. Il doit contenir 'auris-training' (ex: /home/lakhdar/auris-training)."
}

$required = @("backend", "frontend", "manuel", "Dockerfile", ".dockerignore")
foreach ($path in $required) {
  if (-not (Test-Path $path)) {
    throw "Missing required path: $path"
  }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$archive = "auris-deploy-$timestamp.tgz"
$remote = "$ServerUser@$ServerHost"
$remoteArchive = "/tmp/$archive"

Write-Host "Creating archive: $archive"
& tar -czf $archive `
  --exclude=".git" `
  --exclude=".vscode" `
  --exclude="backend/.venv" `
  --exclude="backend/venv" `
  --exclude="frontend/node_modules" `
  --exclude="frontend/dist" `
  --exclude="**/__pycache__" `
  --exclude="**/*.pyc" `
  backend frontend manuel Dockerfile .dockerignore README.md

if ($LASTEXITCODE -ne 0) {
  throw "Archive creation failed"
}

Write-Host "Uploading archive to $remote..."
& scp $archive "${remote}:$remoteArchive"
if ($LASTEXITCODE -ne 0) {
  throw "Upload failed"
}

$remoteCmd = @(
  "set -euo pipefail"
  "mkdir -p '$RemoteDir'"
  "tar -xzf '$remoteArchive' -C '$RemoteDir'"
  "cd '$RemoteDir'"
  "if [ ! -f '$RemoteDir/.env.prod' ]; then echo '.env.prod missing on server'; exit 1; fi"
  "docker build --build-arg VITE_API_URL=$ApiUrl -t '$ImageName' ."
  "docker rm -f '$ContainerName' >/dev/null 2>&1 || true"
  "docker run -d --name '$ContainerName' --restart unless-stopped --env-file '$RemoteDir/.env.prod' -p 127.0.0.1:5002:5002 '$ImageName'"
  "health_ok=0"
  "for i in `$(seq 1 120); do"
  "  if curl -fsS http://127.0.0.1:5002/api/health >/dev/null; then health_ok=1; break; fi"
  "  if ! docker ps --format '{{.Names}}' | grep -q '^$ContainerName$'; then"
  "    echo 'container-not-running'"
  "    docker ps -a --filter name='$ContainerName'"
  "    docker logs --tail 160 '$ContainerName' || true"
  "    exit 1"
  "  fi"
  "  sleep 2"
  "done"
  "if [ `$health_ok -ne 1 ]; then"
  "  echo 'health-check-failed'"
  "  docker logs --tail 160 '$ContainerName' || true"
  "  exit 1"
  "fi"
  "rm -f '$remoteArchive'"
  "echo deploy-ok"
) -join "; "

Write-Host "Deploying on server..."
& ssh $remote $remoteCmd
if ($LASTEXITCODE -ne 0) {
  throw "Remote deploy failed"
}

Remove-Item -Force $archive
Write-Host "Done. App is updated on https://carchat.online"
