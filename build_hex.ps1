# ==============================================================
# build_hex.ps1 — Compile firmware and export .hex
# ==============================================================
# Requirements: arduino-cli installed (run setup_windows.ps1 first)
# Output:       .\output\firmware\wheel_controller.hex
# ==============================================================

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

$SKETCH_DIR  = Join-Path $ROOT "firmware\normal_mode\wheel_controller"
$OUTPUT_DIR  = Join-Path $ROOT "output\firmware"
$HEX_NAME    = "wheel_controller.hex"
$FQBN        = "arduino:avr:leonardo"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  SelfDriveBeamNGTech — Build Firmware .hex" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ---- Find arduino-cli ----
$cliExe = "arduino-cli"
$localCli = Join-Path $ROOT "tools\arduino-cli.exe"
if (Test-Path $localCli) { $cliExe = $localCli }

try {
    $ver = & $cliExe version 2>&1
    Write-Host "arduino-cli: $ver" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: arduino-cli not found. Run .\setup_windows.ps1 first." -ForegroundColor Red
    exit 1
}

# ---- Ensure output directory ----
New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

# ---- Compile ----
Write-Host "Compiling sketch: $SKETCH_DIR" -ForegroundColor Yellow
Write-Host "Target FQBN:      $FQBN" -ForegroundColor Yellow
Write-Host ""

$buildResult = & $cliExe compile `
    --fqbn $FQBN `
    --output-dir "$OUTPUT_DIR" `
    "$SKETCH_DIR" 2>&1

Write-Host $buildResult

# ---- Find and rename .hex ----
# arduino-cli outputs <sketch>.ino.hex
$generatedHex = Get-ChildItem -Path $OUTPUT_DIR -Filter "*.hex" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($null -eq $generatedHex) {
    Write-Host ""
    Write-Host "ERROR: No .hex file found in $OUTPUT_DIR after compilation." -ForegroundColor Red
    Write-Host "       Check compiler output above for errors." -ForegroundColor Red
    exit 1
}

$finalHex = Join-Path $OUTPUT_DIR $HEX_NAME
if ($generatedHex.FullName -ne $finalHex) {
    Copy-Item -Path $generatedHex.FullName -Destination $finalHex -Force
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Output .hex:" -ForegroundColor White
Write-Host "  $finalHex" -ForegroundColor Cyan
Write-Host ""
Write-Host "Flash with: .\flash_hex.ps1 -Port COM3" -ForegroundColor Gray
