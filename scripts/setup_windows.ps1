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

if (Test-Path (Join-Path $repoRoot 'scripts\register_autoac_command.ps1')) {
    Write-Host "[setup] Registering autoac command in PowerShell profile ..."
    & .\scripts\register_autoac_command.ps1
}

Write-Host ""
Write-Host "[setup] Done."
Write-Host "[setup] Next: autoac install-app"
Write-Host "[setup] Then: autoac run -Debug"
