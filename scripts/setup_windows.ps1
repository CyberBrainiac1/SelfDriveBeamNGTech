param(
    [switch]$RecreateVenv
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot '.venv'
$requirementsPath = Join-Path $repoRoot 'requirements.txt'

Write-Host "[setup] Repository root: $repoRoot"
Set-Location $repoRoot

if ($RecreateVenv -and (Test-Path $venvPath)) {
    Write-Host "[setup] Removing existing .venv ..."
    Remove-Item -Recurse -Force $venvPath
}

if (-not (Test-Path $venvPath)) {
    Write-Host "[setup] Creating virtual environment ..."
    python -m venv .venv
} else {
    Write-Host "[setup] Using existing virtual environment."
}

$activateScript = Join-Path $venvPath 'Scripts\Activate.ps1'
if (-not (Test-Path $activateScript)) {
    throw "Activate script not found at $activateScript"
}

Write-Host "[setup] Activating virtual environment ..."
& $activateScript

Write-Host "[setup] Installing dependencies ..."
python -m pip install --upgrade pip
pip install -r $requirementsPath

Write-Host ""
Write-Host "[setup] Done."
Write-Host "[setup] Next: run .\scripts\install_ac_app.ps1"
Write-Host "[setup] Then: run .\scripts\run_classical.ps1 -DebugView"
