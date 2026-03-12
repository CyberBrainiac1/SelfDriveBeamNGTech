# ==============================================================
# run_app.ps1 — Launch the SelfDriveBeamNGTech desktop app
# ==============================================================

param(
    [switch]$BeamNGMode  # Launch directly into BeamNG AI mode
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

$venvPython = Join-Path $ROOT "venv\Scripts\python.exe"
$mainPy     = Join-Path $ROOT "desktop_app\main.py"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  SelfDriveBeamNGTech — Launching Desktop App" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: venv not found. Run .\setup_windows.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $mainPy)) {
    Write-Host "ERROR: desktop_app\main.py not found." -ForegroundColor Red
    exit 1
}

$args_list = @()
if ($BeamNGMode) {
    $args_list += "--beamng-mode"
    Write-Host "Starting in BeamNG AI Mode..." -ForegroundColor Magenta
} else {
    Write-Host "Starting in Normal Mode..." -ForegroundColor Green
}

Write-Host ""
Set-Location $ROOT
& $venvPython $mainPy @args_list
