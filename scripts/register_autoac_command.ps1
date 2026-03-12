$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$dispatcher = Join-Path $repoRoot 'scripts\autoac.ps1'

if (-not (Test-Path $dispatcher)) {
    throw "Dispatcher not found: $dispatcher"
}

function Add-ToUserPath([string]$dir) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ([string]::IsNullOrWhiteSpace($userPath)) {
        $userPath = ''
    }
    $parts = $userPath -split ';' | Where-Object { $_ -and $_.Trim() -ne '' }
    if ($parts -notcontains $dir) {
        $newPath = if ($userPath) { "$userPath;$dir" } else { $dir }
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        if (($env:Path -split ';') -notcontains $dir) {
            $env:Path = "$env:Path;$dir"
        }
        Write-Host "[register] Added to user PATH: $dir"
    } else {
        if (($env:Path -split ';') -notcontains $dir) {
            $env:Path = "$env:Path;$dir"
        }
        Write-Host "[register] PATH already contains: $dir"
    }
}

function Install-Launcher([string]$targetDir, [string]$dispatcherPath) {
    New-Item -ItemType Directory -Force $targetDir | Out-Null

    $cmdLauncher = Join-Path $targetDir 'autoac.cmd'
    $cmdText = "@echo off`r`n" +
               "powershell -NoProfile -ExecutionPolicy Bypass -File `"$dispatcherPath`" %*`r`n"
    Set-Content -Path $cmdLauncher -Value $cmdText -Encoding ASCII

    $ps1Launcher = Join-Path $targetDir 'autoac.ps1'
    $ps1Text = "param([Parameter(ValueFromRemainingArguments=`$true)][string[]]`$Args)`n" +
               "& '$dispatcherPath' @Args`n"
    Set-Content -Path $ps1Launcher -Value $ps1Text -Encoding ASCII

    Write-Host "[register] Installed launchers:"
    Write-Host "  $cmdLauncher"
    Write-Host "  $ps1Launcher"
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

$launcherDir = Join-Path $env:USERPROFILE '.autoac\bin'
Install-Launcher -targetDir $launcherDir -dispatcherPath $dispatcher
Add-ToUserPath -dir $launcherDir

Write-Host "[register] You can now run: autoac help"
Write-Host "[register] If current terminal still doesn't see it, open a new terminal window."
