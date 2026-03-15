param(
    [switch]$Force,
    [switch]$SkipBuild,
    [switch]$SkipApiChecks,
    [switch]$SkipImageProcessing,
    [switch]$NoOcr,
    [int]$OcrMaxPages = 0,
    [string]$OcrLang = "fra+eng+kor"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path $scriptDir
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$summaryPath = Join-Path $backendDir "data\last_update_summary.json"

Write-Host ("=" * 70)
Write-Host "Auris update_car_data - start"
Write-Host "Project: $projectRoot"
Write-Host ("=" * 70)

function Ensure-UserPathContains {
    param([string]$DirPath)

    if (-not (Test-Path $DirPath)) {
        return
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) {
        $parts = $userPath -split ";" | Where-Object { $_ -ne "" }
    }

    if ($parts -contains $DirPath) {
        return
    }

    $updated = if ($userPath -and -not $userPath.EndsWith(";")) {
        "$userPath;$DirPath"
    }
    elseif ($userPath) {
        "$userPath$DirPath"
    }
    else {
        $DirPath
    }

    [Environment]::SetEnvironmentVariable("Path", $updated, "User")
}

function Ensure-TesseractLanguage {
    param(
        [string]$LangCode,
        [string]$TargetTessDataDir,
        [string]$InstallTessDataDir
    )

    $safeCode = "$LangCode".Trim().ToLower()
    if (-not $safeCode) {
        return
    }

    $targetFile = Join-Path $TargetTessDataDir "$safeCode.traineddata"
    if (Test-Path $targetFile) {
        return
    }

    $installFile = Join-Path $InstallTessDataDir "$safeCode.traineddata"
    if (Test-Path $installFile) {
        Copy-Item -Path $installFile -Destination $targetFile -Force
        Write-Host "Language '$safeCode' installed from local tesseract data."
        return
    }

    $url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$safeCode.traineddata"
    try {
        Invoke-WebRequest -Uri $url -OutFile $targetFile -Headers @{ "User-Agent" = "AurisTrainingBot/1.0" }
        Write-Host "Language '$safeCode' downloaded from tessdata_fast."
    }
    catch {
        Write-Warning "Could not install language '$safeCode': $($_.Exception.Message)"
    }
}

Write-Host "`n[1/6] Checking OCR runtime and language packs..."
$defaultTesseractDir = "C:\Program Files\Tesseract-OCR"
$defaultTesseractExe = Join-Path $defaultTesseractDir "tesseract.exe"
$defaultTessDataDir = Join-Path $defaultTesseractDir "tessdata"
$userTessRoot = Join-Path $env:LOCALAPPDATA "Tesseract-OCR"
$userTessData = Join-Path $userTessRoot "tessdata"

if ((Test-Path $defaultTesseractExe) -and ($env:Path -notmatch [Regex]::Escape($defaultTesseractDir))) {
    $env:Path = "$defaultTesseractDir;$env:Path"
}

Ensure-UserPathContains -DirPath $defaultTesseractDir

$tesseractCmd = Get-Command tesseract -ErrorAction SilentlyContinue
if ($NoOcr) {
    Write-Host "OCR explicitly disabled (--NoOcr)."
}
elseif (-not $tesseractCmd) {
    Write-Warning "Tesseract binary not found. Scanned PDFs may fail extraction and will be excluded."
    Write-Host "Install Tesseract to enable full OCR fallback."
}
else {
    New-Item -ItemType Directory -Force -Path $userTessData | Out-Null

    foreach ($baseLang in @("eng", "osd")) {
        Ensure-TesseractLanguage -LangCode $baseLang -TargetTessDataDir $userTessData -InstallTessDataDir $defaultTessDataDir
    }

    $requestedLangs = $OcrLang -split "\+" | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ } | Select-Object -Unique
    foreach ($langCode in $requestedLangs) {
        Ensure-TesseractLanguage -LangCode $langCode -TargetTessDataDir $userTessData -InstallTessDataDir $defaultTessDataDir
    }

    [Environment]::SetEnvironmentVariable("TESSDATA_PREFIX", $userTessData, "User")
    $env:TESSDATA_PREFIX = $userTessData

    Write-Host "Tesseract found: $($tesseractCmd.Source)"
    Write-Host "TESSDATA_PREFIX: $($env:TESSDATA_PREFIX)"
    tesseract --list-langs
}

Write-Host "`n[2/6] Installing/refreshing Python dependencies..."
Push-Location $backendDir
python -m pip install -q rank-bm25 pypdf pymupdf pytesseract pillow rembg onnxruntime duckduckgo-search
Pop-Location

if (-not $SkipImageProcessing) {
    Write-Host "`n[3/6] Removing image backgrounds (vehicle cutouts)..."
    Push-Location $backendDir
    python -m process_vehicle_images
    $imgExit = $LASTEXITCODE
    Pop-Location

    if ($imgExit -ne 0) {
        throw "Image processing failed with exit code $imgExit"
    }
}
else {
    Write-Host "[3/6] Image processing skipped (--SkipImageProcessing)."
}

Write-Host "`n[4/6] Running incremental indexing from car data..."
$indexArgs = @("-m", "index_manuals", "--summary-json", $summaryPath, "--ocr-lang", $OcrLang, "--ocr-max-pages", "$OcrMaxPages")
if ($Force) { $indexArgs += "--force" }
if ($NoOcr) { $indexArgs += "--no-ocr" }

Push-Location $backendDir
python @indexArgs
$indexExit = $LASTEXITCODE
Pop-Location

if ($indexExit -ne 0) {
    throw "Indexing failed with exit code $indexExit"
}

if (-not (Test-Path $summaryPath)) {
    throw "Summary file was not created: $summaryPath"
}

$summary = Get-Content -Raw $summaryPath | ConvertFrom-Json

function Show-Group {
    param(
        [string]$Title,
        [object[]]$Items
    )

    if (-not $Items) { $Items = @() }
    Write-Host "`n$Title ($($Items.Count))"
    foreach ($item in $Items) {
        $reason = ""
        if ($item.PSObject.Properties.Name -contains "reason" -and $item.reason) {
            $reason = " -> $($item.reason)"
        }
        Write-Host " - [$($item.brand)] $($item.name) ($($item.slug))$reason"
    }
}

Write-Host "`n================ Indexing Report ================"
Write-Host "Source mode: $($summary.source_mode)"
Write-Host "PDFs discovered: $($summary.discovered_total)"
Show-Group -Title "Indexed new" -Items $summary.indexed_new
Show-Group -Title "Re-indexed changed" -Items $summary.reindexed
Show-Group -Title "Skipped unchanged (no re-RAG)" -Items $summary.skipped_unchanged
Show-Group -Title "Failed extraction / not added" -Items $summary.failed
Show-Group -Title "Removed after failed extraction" -Items $summary.removed_failed
Show-Group -Title "Removed because source missing" -Items $summary.removed_missing

Write-Host "`nChats added/updated: $($summary.chat_added.Count)"
Write-Host "Chats already available: $($summary.chat_already_available.Count)"
Write-Host "Chats removed: $($summary.chat_removed.Count)"
Write-Host "Manifest total guides: $($summary.manifest_total)"
Write-Host "Summary JSON: $summaryPath"
Write-Host "===============================================`n"

if (-not $SkipBuild) {
    Write-Host "[5/6] Building frontend..."
    Push-Location $frontendDir
    npm run build
    $buildExit = $LASTEXITCODE
    Pop-Location

    if ($buildExit -ne 0) {
        throw "Frontend build failed with exit code $buildExit"
    }
}
else {
    Write-Host "[5/6] Frontend build skipped (--SkipBuild)."
}

if (-not $SkipApiChecks) {
    Write-Host "`n[6/6] Running API sanity checks..."
    Push-Location $backendDir
    $summaryEscaped = $summaryPath -replace "\\", "\\\\"
    $pythonCheck = @"
import json
from pathlib import Path
from api import app

summary_path = Path("$summaryEscaped")
if not summary_path.exists():
    raise SystemExit(f"Summary not found: {summary_path}")

summary = json.loads(summary_path.read_text(encoding="utf-8"))

client = app.test_client()
resp = client.get("/api/guides")
if resp.status_code != 200:
    raise SystemExit(f"/api/guides failed with status {resp.status_code}")

data = resp.get_json() or {}
if not data.get("success"):
    raise SystemExit("/api/guides returned success=false")

guides = data.get("guides", [])
slugs_in_api = {g.get("slug") for g in guides}

check_items = []
check_items.extend(summary.get("indexed_new", []))
check_items.extend(summary.get("reindexed", []))
check_items.extend(summary.get("skipped_unchanged", []))

errors = []
for item in check_items:
    slug = item.get("slug")
    if slug not in slugs_in_api:
        errors.append(f"Guide missing in /api/guides: {slug}")
        continue

    detail = client.get(f"/api/guides/{slug}")
    if detail.status_code != 200:
        errors.append(f"/api/guides/{slug} failed ({detail.status_code})")
        continue

    history = client.get(f"/api/guides/{slug}/history")
    if history.status_code != 200:
        errors.append(f"/api/guides/{slug}/history failed ({history.status_code})")

if errors:
    for err in errors:
        print(f"API CHECK ERROR: {err}")
    raise SystemExit(1)

print(f"API checks passed. Guides visible: {len(guides)}")
"@
    $pythonCheck | python -
    $apiExit = $LASTEXITCODE
    Pop-Location

    if ($apiExit -ne 0) {
        throw "API checks failed with exit code $apiExit"
    }
}
else {
    Write-Host "[6/6] API checks skipped (--SkipApiChecks)."
}

Write-Host "`nDone. One-command update completed successfully."
Write-Host "Run again any time after adding PDFs under car data/<brand>/."
