param(
    [switch]$DebugView,
    [double]$TargetSpeed
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$activateScript = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $activateScript)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

& $activateScript

$args = @('.\main.py', '--mode', 'neural')
if ($DebugView) { $args += '--debug' }
if ($PSBoundParameters.ContainsKey('TargetSpeed')) {
    $args += @('--target-speed', "$TargetSpeed")
}

Write-Host "[run-neural] python $($args -join ' ')"
python @args
