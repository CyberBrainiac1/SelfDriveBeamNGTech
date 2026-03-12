$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

$src = Join-Path $repoRoot 'ac_app\ACDriverApp'
$dstParent = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\apps\python'
$dst = Join-Path $dstParent 'ACDriverApp'

if (-not (Test-Path $src)) {
    throw "Source folder not found: $src"
}

Write-Host "[install-app] Creating target folder: $dstParent"
New-Item -ItemType Directory -Force $dstParent | Out-Null

Write-Host "[install-app] Copying ACDriverApp ..."
Copy-Item -Recurse -Force $src $dstParent

$mainFile = Join-Path $dst 'ACDriverApp.py'
$iniFile = Join-Path $dst 'ui\ACDriverApp.ini'

Write-Host "[install-app] Verify files:"
Write-Host "  $mainFile => $(Test-Path $mainFile)"
Write-Host "  $iniFile  => $(Test-Path $iniFile)"

Write-Host ""
Write-Host "[install-app] Done. In Assetto Corsa enable ACDriverApp in UI Modules."
