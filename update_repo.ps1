# ==============================================================
# update_repo.ps1 — Pull latest changes from GitHub
# ==============================================================
# Updates the local codebase, rebuilds the hex if needed,
# and prints a changelog summary.
# ==============================================================

param(
    [switch]$RebuildHex,     # Force rebuild firmware after update
    [switch]$UpdateDeps      # Re-run pip install after update
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  SelfDriveBeamNGTech — Update from GitHub" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ---- Check git ----
try {
    git --version | Out-Null
} catch {
    Write-Host "ERROR: git not found. Install Git from https://git-scm.com" -ForegroundColor Red
    exit 1
}

Set-Location $ROOT

# ---- Show current version ----
$currentCommit = git rev-parse --short HEAD 2>&1
Write-Host "Current commit: $currentCommit" -ForegroundColor Gray

# ---- Pull ----
Write-Host "Pulling latest changes..." -ForegroundColor Yellow
git fetch origin 2>&1
git pull --rebase 2>&1

$newCommit = git rev-parse --short HEAD 2>&1
Write-Host "Updated to:     $newCommit" -ForegroundColor Green

# ---- Show changelog ----
Write-Host ""
Write-Host "--- Recent changes ---" -ForegroundColor White
git log --oneline -10 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

# ---- Update Python deps if requested or requirements.txt changed ----
$reqChanged = git diff "HEAD@{1}" HEAD --name-only 2>&1 | Select-String "requirements.txt"
if ($UpdateDeps -or $reqChanged) {
    $venvPip = Join-Path $ROOT "venv\Scripts\pip.exe"
    if (Test-Path $venvPip) {
        Write-Host ""
        Write-Host "Updating Python dependencies..." -ForegroundColor Yellow
        & $venvPip install -r (Join-Path $ROOT "requirements.txt") --quiet
        Write-Host "Dependencies updated." -ForegroundColor Green
    }
}

# ---- Rebuild hex if requested or firmware changed ----
$fwChanged = git diff "HEAD@{1}" HEAD --name-only 2>&1 | Select-String "firmware\\"
if ($RebuildHex -or $fwChanged) {
    Write-Host ""
    Write-Host "Firmware files changed — rebuilding .hex..." -ForegroundColor Yellow
    & (Join-Path $ROOT "build_hex.ps1")
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Update complete: $currentCommit -> $newCommit" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Launch the app: .\run_app.ps1" -ForegroundColor Gray
