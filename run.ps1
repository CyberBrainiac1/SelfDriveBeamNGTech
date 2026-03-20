#Requires -Version 5.1
<#
.SYNOPSIS
    BeamNG.tech self-driving system — main entry point.
.DESCRIPTION
    Validates environment, checks dependencies, and launches the self-driving
    controller on hirochi_raceway via BeamNG.tech.
.PARAMETER Config
    Path to a YAML config file. Defaults to config/hirochi_endurance.yaml.
.PARAMETER BeamNGHome
    Override BeamNG.tech install path. Defaults to C:\Beamngtech\BeamNG.tech.v0.38.3.0
.PARAMETER DryRun
    Run startup diagnostics only — do not launch BeamNG.
.PARAMETER Stage
    Control which stage to run: 'full' (default), 'diagnostics', 'calibrate'.
.EXAMPLE
    .\run.ps1
.EXAMPLE
    .\run.ps1 -Config config\hirochi_endurance.yaml -Stage diagnostics
.EXAMPLE
    .\run.ps1 -BeamNGHome "C:\Beamngtech\BeamNG.tech.v0.38.3.0" -DryRun
#>
param(
    [string]$Config     = "config\hirochi_endurance.yaml",
    [string]$BeamNGHome = "C:\Beamngtech\BeamNG.tech.v0.38.3.0",
    [switch]$DryRun,
    [ValidateSet("full","diagnostics","calibrate")]
    [string]$Stage      = "full"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Banner ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  BeamNG.tech Self-Drive System" -ForegroundColor Cyan
Write-Host "  Stage: $Stage" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── Working directory ──────────────────────────────────────────────────────
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

# ── 1. Validate BeamNG.tech path ───────────────────────────────────────────
Write-Host "[1/5] Checking BeamNG.tech path..." -ForegroundColor Yellow
$BeamNGExe = Join-Path $BeamNGHome "BeamNG.tech.exe"
if (-not (Test-Path $BeamNGExe)) {
    Write-Host "ERROR: BeamNG.tech.exe not found at: $BeamNGExe" -ForegroundColor Red
    Write-Host "       Set -BeamNGHome to your BeamNG.tech install directory." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $BeamNGExe" -ForegroundColor Green

# ── 2. Validate Python ─────────────────────────────────────────────────────
Write-Host "[2/5] Checking Python..." -ForegroundColor Yellow
try {
    $PyVersion = & python --version 2>&1
    Write-Host "  OK: $PyVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found on PATH." -ForegroundColor Red
    exit 1
}

# ── 3. Validate core dependencies ─────────────────────────────────────────
Write-Host "[3/5] Checking Python dependencies..." -ForegroundColor Yellow
$Deps = @("beamngpy", "numpy", "yaml", "scipy")
$Missing = @()
foreach ($dep in $Deps) {
    $check = & python -c "import $dep" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $Missing += $dep
    }
}
if ($Missing.Count -gt 0) {
    Write-Host "  Missing packages: $($Missing -join ', ')" -ForegroundColor Red
    Write-Host "  Run:  pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK: beamngpy, numpy, scipy, pyyaml" -ForegroundColor Green

# ── 4. Validate config file ────────────────────────────────────────────────
Write-Host "[4/5] Checking config: $Config..." -ForegroundColor Yellow
if (-not (Test-Path $Config)) {
    Write-Host "ERROR: Config file not found: $Config" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $Config" -ForegroundColor Green

# ── 5. Create output directories ──────────────────────────────────────────
Write-Host "[5/5] Ensuring output directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "output\logs"        | Out-Null
New-Item -ItemType Directory -Force -Path "output\diagnostics" | Out-Null
Write-Host "  OK: output/logs, output/diagnostics" -ForegroundColor Green

Write-Host ""

# ── Dry-run exit ───────────────────────────────────────────────────────────
if ($DryRun) {
    Write-Host "Dry-run complete. All checks passed." -ForegroundColor Green
    exit 0
}

# ── Launch ─────────────────────────────────────────────────────────────────
Write-Host "Launching self-drive controller..." -ForegroundColor Cyan
Write-Host ""

$PythonArgs = @(
    "src\main.py",
    "--config", $Config,
    "--beamng-home", $BeamNGHome,
    "--stage", $Stage
)

& python @PythonArgs
$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "Session ended cleanly." -ForegroundColor Green
} else {
    Write-Host "Session exited with code $ExitCode. Check output/logs/ for details." -ForegroundColor Red
}
exit $ExitCode
