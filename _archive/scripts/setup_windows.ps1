# ==============================================================
# setup_windows.ps1 — SelfDriveBeamNGTech Windows Setup Script
# Run once to configure your environment.
# Run as Administrator for best results.
# ==============================================================

param(
    [switch]$SkipArduinoCLI,
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  SelfDriveBeamNGTech — Windows Setup" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ---- 1. Check Python ----
if (-not $SkipPython) {
    Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
    try {
        $pyVer = python --version 2>&1
        Write-Host "      Found: $pyVer" -ForegroundColor Green
    } catch {
        Write-Host "      ERROR: Python not found. Install from https://python.org (3.10+, check 'Add to PATH')" -ForegroundColor Red
        exit 1
    }

    # ---- 2. Create venv ----
    Write-Host "[2/6] Creating Python virtual environment..." -ForegroundColor Yellow
    $venvPath = Join-Path $ROOT "venv"
    if (Test-Path $venvPath) {
        Write-Host "      venv already exists, skipping." -ForegroundColor Gray
    } else {
        python -m venv "$venvPath"
        Write-Host "      Created venv at $venvPath" -ForegroundColor Green
    }

    # ---- 3. Install Python dependencies ----
    Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow
    $pip = Join-Path $venvPath "Scripts\pip.exe"
    & $pip install --upgrade pip --quiet
    & $pip install -r (Join-Path $ROOT "requirements.txt")
    Write-Host "      Dependencies installed." -ForegroundColor Green
} else {
    Write-Host "[1-3/6] Skipping Python setup (--SkipPython)" -ForegroundColor Gray
}

# ---- 4. Check / Install arduino-cli ----
if (-not $SkipArduinoCLI) {
    Write-Host "[4/6] Checking arduino-cli..." -ForegroundColor Yellow
    $arduinoCliPath = Join-Path $ROOT "tools\arduino-cli.exe"

    $arduinoFound = $false
    try {
        $arVer = arduino-cli version 2>&1
        Write-Host "      Found in PATH: $arVer" -ForegroundColor Green
        $arduinoFound = $true
    } catch {}

    if (-not $arduinoFound) {
        if (Test-Path $arduinoCliPath) {
            Write-Host "      Found local: $arduinoCliPath" -ForegroundColor Green
            $arduinoFound = $true
        }
    }

    if (-not $arduinoFound) {
        Write-Host "      arduino-cli not found. Downloading..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path (Join-Path $ROOT "tools") | Out-Null
        $url = "https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip"
        $zipPath = Join-Path $ROOT "tools\arduino-cli.zip"
        Invoke-WebRequest -Uri $url -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath (Join-Path $ROOT "tools") -Force
        Remove-Item $zipPath
        Write-Host "      arduino-cli downloaded to tools\" -ForegroundColor Green
    }

    # ---- 5. Install Leonardo core ----
    Write-Host "[5/6] Installing Arduino Leonardo (AVR) core..." -ForegroundColor Yellow
    $cliExe = if (Test-Path $arduinoCliPath) { $arduinoCliPath } else { "arduino-cli" }

    & $cliExe core update-index 2>&1 | Out-Null
    & $cliExe core install "arduino:avr" 2>&1
    Write-Host "      Arduino AVR core ready." -ForegroundColor Green
} else {
    Write-Host "[4-5/6] Skipping arduino-cli setup (--SkipArduinoCLI)" -ForegroundColor Gray
}

# ---- 6. Create output folders ----
Write-Host "[6/6] Preparing output directories..." -ForegroundColor Yellow
@("output\firmware", "output\logs", "output\profiles") | ForEach-Object {
    $p = Join-Path $ROOT $_
    New-Item -ItemType Directory -Force -Path $p | Out-Null
}
Write-Host "      Output directories ready." -ForegroundColor Green

# ---- Done ----
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Build firmware:    .\build_hex.ps1"
Write-Host "  2. Flash firmware:    .\flash_hex.ps1  (connect Arduino first)"
Write-Host "  3. Launch desktop UI: .\run_app.ps1"
Write-Host "  4. Run diagnostics:   .\diagnose.ps1"
Write-Host ""
