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

$remoteScript = @'
set -euo pipefail
mkdir -p '__REMOTE_DIR__'
case '__REMOTE_DIR__' in *auris-training*) ;; *) echo 'unsafe-remote-dir'; exit 1 ;; esac
find '__REMOTE_DIR__' -mindepth 1 -maxdepth 1 ! -name '.env.prod' -exec rm -rf {} +
tar -xzf '__REMOTE_ARCHIVE__' -C '__REMOTE_DIR__'
cd '__REMOTE_DIR__'
if [ ! -f '__REMOTE_DIR__/.env.prod' ]; then echo '.env.prod missing on server'; exit 1; fi
docker build --build-arg VITE_API_URL=__API_URL__ -t '__IMAGE_NAME__' .
docker rm -f '__CONTAINER_NAME__' >/dev/null 2>&1 || true
docker run -d --name '__CONTAINER_NAME__' --restart unless-stopped --env-file '__REMOTE_DIR__/.env.prod' -p 127.0.0.1:5002:3000 '__IMAGE_NAME__'
health_ok=0
for i in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:5002/api/health >/dev/null; then health_ok=1; break; fi
  if ! docker ps --format '{{.Names}}' | grep -q '^__CONTAINER_NAME__$'; then
    echo 'container-not-running'
    docker ps -a --filter name='__CONTAINER_NAME__'
    docker logs --tail 160 '__CONTAINER_NAME__' || true
    exit 1
  fi
  sleep 2
done
if [ $health_ok -ne 1 ]; then
  echo 'health-check-failed'
  docker logs --tail 160 '__CONTAINER_NAME__' || true
  exit 1
fi
rm -f '__REMOTE_ARCHIVE__'
echo deploy-ok
'@

$remoteScript = $remoteScript.Replace("__REMOTE_DIR__", $RemoteDir)
$remoteScript = $remoteScript.Replace("__REMOTE_ARCHIVE__", $remoteArchive)
$remoteScript = $remoteScript.Replace("__API_URL__", $ApiUrl)
$remoteScript = $remoteScript.Replace("__IMAGE_NAME__", $ImageName)
$remoteScript = $remoteScript.Replace("__CONTAINER_NAME__", $ContainerName)
$remoteScript = $remoteScript -replace "`r`n", "`n"

Write-Host "Deploying on server..."
$remoteScript | & ssh $remote "bash -s"
if ($LASTEXITCODE -ne 0) {
  throw "Remote deploy failed"
}

Remove-Item -Force $archive
Write-Host "Done. App is updated on https://carchat.online"
