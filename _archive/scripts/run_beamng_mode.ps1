# ==============================================================
# run_beamng_mode.ps1 — Launch app directly in BeamNG AI mode
# ==============================================================

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "  SelfDriveBeamNGTech — BeamNG AI Mode" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Launching BeamNG.tech AI mode..." -ForegroundColor Magenta
Write-Host ""

& (Join-Path $ROOT "run_app.ps1") -BeamNGMode
