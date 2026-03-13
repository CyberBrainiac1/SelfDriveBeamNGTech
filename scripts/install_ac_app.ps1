$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

$src = Join-Path $repoRoot 'ac_app\ACDriverApp'

function Get-DefaultGameRoot {
    $candidates = @(
        'C:\Program Files (x86)\Steam\steamapps\common\assettocorsa',
        'C:\Program Files\Steam\steamapps\common\assettocorsa'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

$gameRoot = Get-DefaultGameRoot
$primaryDstParent = if ($gameRoot) {
    Join-Path $gameRoot 'apps\python'
} else {
    $null
}

$fallbackDstParent = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\apps\python'
$installTargets = @()
if ($primaryDstParent) {
    $installTargets += $primaryDstParent
}
$installTargets += $fallbackDstParent

$installedTo = @()

if (-not (Test-Path $src)) {
    throw "Source folder not found: $src"
}

if (-not $primaryDstParent) {
    Write-Host "[install-app] Could not auto-detect Assetto Corsa game root."
    Write-Host "[install-app] Will install fallback copy to Documents path only."
}

foreach ($dstParent in $installTargets) {
    $dst = Join-Path $dstParent 'ACDriverApp'

    try {
        Write-Host "[install-app] Creating target folder: $dstParent"
        New-Item -ItemType Directory -Force $dstParent | Out-Null

        Write-Host "[install-app] Copying ACDriverApp -> $dstParent"
        Copy-Item -Recurse -Force $src $dstParent

        $mainFile = Join-Path $dst 'ACDriverApp.py'
        $iniFile = Join-Path $dst 'ui\ACDriverApp.ini'

        Write-Host "[install-app] Verify files in ${dstParent}:"
        Write-Host "  $mainFile => $(Test-Path $mainFile)"
        Write-Host "  $iniFile  => $(Test-Path $iniFile)"

        if ((Test-Path $mainFile) -and (Test-Path $iniFile)) {
            $installedTo += $dstParent
        }
    } catch {
        Write-Warning "[install-app] Failed at $dstParent : $($_.Exception.Message)"
        if ($dstParent -eq $primaryDstParent) {
            Write-Host "[install-app] Tip: If this is under Program Files, run PowerShell as Administrator and retry."
        }
    }
}

if ($installedTo.Count -eq 0) {
    throw "ACDriverApp was not installed to any target path."
}

Write-Host ""
Write-Host "[install-app] Installed to:"
$installedTo | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "[install-app] Done. In Assetto Corsa enable ACDriverApp in UI Modules."
