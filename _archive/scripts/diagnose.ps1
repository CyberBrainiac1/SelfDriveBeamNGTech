# ==============================================================
# diagnose.ps1 — SelfDriveBeamNGTech Diagnostics
# ==============================================================
# Checks your environment and prints a clear status report.
# ==============================================================

$ROOT = $PSScriptRoot
$passed = 0
$failed = 0

function Check($label, $ok, $detail = "") {
    if ($ok) {
        Write-Host "  [OK]  $label" -ForegroundColor Green
        if ($detail) { Write-Host "        $detail" -ForegroundColor Gray }
        $script:passed++
    } else {
        Write-Host "  [!!]  $label" -ForegroundColor Red
        if ($detail) { Write-Host "        $detail" -ForegroundColor Yellow }
        $script:failed++
    }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  SelfDriveBeamNGTech — Diagnostics" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ---- Python ----
Write-Host "--- Python ---" -ForegroundColor White
try {
    $pyVer = python --version 2>&1
    Check "Python installed" $true "$pyVer"
} catch {
    Check "Python installed" $false "Install from https://python.org"
}

# ---- venv ----
$venvPy = Join-Path $ROOT "venv\Scripts\python.exe"
Check "venv exists" (Test-Path $venvPy) "Expected: $venvPy"

# ---- Python packages ----
if (Test-Path $venvPy) {
    Write-Host ""
    Write-Host "--- Python Packages ---" -ForegroundColor White
    $packages = @("PySide6", "serial", "beamngpy", "numpy", "scipy", "pydantic", "loguru")
    foreach ($pkg in $packages) {
        try {
            $out = & $venvPy -c "import importlib; importlib.import_module('$pkg')" 2>&1
            Check "Python: $pkg" ($LASTEXITCODE -eq 0) ""
        } catch {
            Check "Python: $pkg" $false "pip install $pkg"
        }
    }
}

# ---- arduino-cli ----
Write-Host ""
Write-Host "--- Arduino CLI ---" -ForegroundColor White
$cliExe = "arduino-cli"
$localCli = Join-Path $ROOT "tools\arduino-cli.exe"
if (Test-Path $localCli) { $cliExe = $localCli }

try {
    $arVer = & $cliExe version 2>&1
    Check "arduino-cli found" $true "$arVer"
    # Check Leonardo core
    $cores = & $cliExe core list 2>&1
    $hasAvr = $cores -match "arduino:avr"
    Check "Arduino AVR core installed" $hasAvr "arduino:avr"
} catch {
    Check "arduino-cli found" $false "Run .\setup_windows.ps1"
}

# ---- Firmware ----
Write-Host ""
Write-Host "--- Firmware ---" -ForegroundColor White
$sketchFile = Join-Path $ROOT "firmware\normal_mode\wheel_controller\wheel_controller.ino"
$hexFile    = Join-Path $ROOT "output\firmware\wheel_controller.hex"
Check "Sketch file exists" (Test-Path $sketchFile) $sketchFile
Check "Built .hex exists"  (Test-Path $hexFile)    "$hexFile  (run .\build_hex.ps1 to build)"

# ---- Serial ports ----
Write-Host ""
Write-Host "--- Serial / COM Ports ---" -ForegroundColor White
try {
    $ports = [System.IO.Ports.SerialPort]::GetPortNames()
    if ($ports.Count -gt 0) {
        Check "COM ports available" $true ($ports -join ", ")
    } else {
        Check "COM ports available" $false "No COM ports detected. Check USB connection."
    }
} catch {
    Check "COM ports available" $false "Could not enumerate ports: $_"
}

# Try arduino-cli board list for Leonardo
try {
    $cliBoards = & $cliExe board list 2>&1
    $leonardoFound = $cliBoards -match "Leonardo"
    Check "Arduino Leonardo detected" $leonardoFound ($cliBoards | Select-String "Leonardo" | Select-Object -First 1)
} catch {}

# ---- Output folders ----
Write-Host ""
Write-Host "--- Output Folders ---" -ForegroundColor White
@("output\firmware", "output\logs", "output\profiles") | ForEach-Object {
    $p = Join-Path $ROOT $_
    Check "Folder: $_" (Test-Path $p) $p
}

# ---- Desktop app files ----
Write-Host ""
Write-Host "--- Desktop App ---" -ForegroundColor White
$appFiles = @(
    "desktop_app\main.py",
    "desktop_app\app.py",
    "desktop_app\core\serial_manager.py",
    "desktop_app\beamng\beamng_manager.py"
)
foreach ($f in $appFiles) {
    $p = Join-Path $ROOT $f
    Check "App file: $f" (Test-Path $p)
}

# ---- Summary ----
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Results: $passed passed, $failed failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
if ($failed -gt 0) {
    Write-Host "Fix issues above, then run .\setup_windows.ps1 if needed." -ForegroundColor Yellow
} else {
    Write-Host "All checks passed! You are ready to go." -ForegroundColor Green
}
Write-Host ""
