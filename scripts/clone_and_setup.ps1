param(
    [string]$RepoUrl = "https://github.com/CyberBrainiac1/SelfDriveBeamNGTech.git",
    [string]$InstallRoot = "",
    [switch]$InstallAcApp
)

$ErrorActionPreference = 'Stop'

function Test-IsAdmin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    if (Test-IsAdmin) {
        $InstallRoot = Join-Path $env:ProgramFiles 'SelfDrive'
    } else {
        $InstallRoot = Join-Path $env:USERPROFILE 'SelfDrive'
    }
}

$repoName = 'SelfDriveBeamNGTech'
$repoPath = Join-Path $InstallRoot $repoName

Write-Host "[bootstrap] Install root: $InstallRoot"
Write-Host "[bootstrap] Repo path   : $repoPath"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed. Install Git for Windows first: https://git-scm.com/download/win"
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not installed or not in PATH. Install Python 3.9+: https://www.python.org/downloads/"
}

if (-not (Test-Path $InstallRoot)) {
    Write-Host "[bootstrap] Creating install root ..."
    New-Item -ItemType Directory -Force $InstallRoot | Out-Null
}

if (-not (Test-Path $repoPath)) {
    Write-Host "[bootstrap] Cloning repository ..."
    git clone $RepoUrl $repoPath
} else {
    Write-Host "[bootstrap] Repository already exists. Pulling latest ..."
    git -C $repoPath pull
}

Set-Location $repoPath
Write-Host "[bootstrap] Running setup_windows.ps1 ..."
& .\scripts\setup_windows.ps1

if ($InstallAcApp) {
    Write-Host "[bootstrap] Installing AC app files ..."
    & .\scripts\install_ac_app.ps1
}

Write-Host ""
Write-Host "[bootstrap] Done."
Write-Host "[bootstrap] Next steps:"
Write-Host "  1) Start Assetto Corsa and enable ACDriverApp in UI Modules"
Write-Host "  2) Run: .\scripts\run_classical.ps1 -DebugView"
