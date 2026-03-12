# ==============================================================
# flash_hex.ps1 — Flash wheel_controller.hex to Arduino Leonardo
# ==============================================================
# Usage: .\flash_hex.ps1 -Port COM3
# Tip:   Run diagnose.ps1 to find your COM port first.
# ==============================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Port = "",

    [Parameter(Mandatory=$false)]
    [string]$HexPath = ""
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$FQBN = "arduino:avr:leonardo"

if ($HexPath -eq "") {
    $HexPath = Join-Path $ROOT "output\firmware\wheel_controller.hex"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  SelfDriveBeamNGTech — Flash Firmware" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ---- Find arduino-cli ----
$cliExe = "arduino-cli"
$localCli = Join-Path $ROOT "tools\arduino-cli.exe"
if (Test-Path $localCli) { $cliExe = $localCli }

# ---- Check hex exists ----
if (-not (Test-Path $HexPath)) {
    Write-Host "ERROR: .hex not found at $HexPath" -ForegroundColor Red
    Write-Host "       Run .\build_hex.ps1 first." -ForegroundColor Red
    exit 1
}
Write-Host "Hex file: $HexPath" -ForegroundColor Green

# ---- Find port if not specified ----
if ($Port -eq "") {
    Write-Host "Detecting COM ports..." -ForegroundColor Yellow
    $boards = & $cliExe board list 2>&1
    Write-Host $boards

    $leonardoLine = $boards | Where-Object { $_ -match "Leonardo" -or $_ -match "32U4" }
    if ($leonardoLine) {
        $Port = ($leonardoLine -split "\s+")[0]
        Write-Host "Auto-detected: $Port" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "ERROR: Could not auto-detect Leonardo port." -ForegroundColor Red
        Write-Host "       Run with: .\flash_hex.ps1 -Port COM3" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "Port: $Port" -ForegroundColor Yellow
Write-Host ""

# ---- Flash ----
Write-Host "Flashing..." -ForegroundColor Yellow
& $cliExe upload `
    --fqbn $FQBN `
    --port $Port `
    --input-file "$HexPath" 2>&1

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  FLASH COMPLETE" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Wheel controller firmware flashed to $Port" -ForegroundColor White
Write-Host "Launch the desktop app: .\run_app.ps1" -ForegroundColor Gray
