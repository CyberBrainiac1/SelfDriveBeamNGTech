param(
    [int]$Epochs = 30,
    [int]$BatchSize = 32
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$activateScript = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $activateScript)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

& $activateScript

Write-Host "[train] Epochs=$Epochs BatchSize=$BatchSize"
python .\scripts\train.py --epochs $Epochs --batch-size $BatchSize
