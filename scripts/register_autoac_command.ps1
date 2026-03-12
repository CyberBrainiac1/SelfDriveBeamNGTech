$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$dispatcher = Join-Path $repoRoot 'scripts\autoac.ps1'

if (-not (Test-Path $dispatcher)) {
    throw "Dispatcher not found: $dispatcher"
}

$profilePath = $PROFILE
$profileDir = Split-Path -Parent $profilePath
if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Force $profileDir | Out-Null
}
if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Force $profilePath | Out-Null
}

$marker = '# autoac command registration'
$content = Get-Content $profilePath -Raw
if ($content -notmatch [regex]::Escape($marker)) {
    Add-Content -Path $profilePath -Value "`n$marker"
    Add-Content -Path $profilePath -Value "function autoac { param([Parameter(ValueFromRemainingArguments=`$true)][string[]]`$Args) & '$dispatcher' @Args }"
    Write-Host "[register] Added autoac function to profile: $profilePath"
} else {
    Write-Host "[register] autoac is already registered in profile: $profilePath"
}

Write-Host "[register] Open a new PowerShell window, then run: autoac help"
