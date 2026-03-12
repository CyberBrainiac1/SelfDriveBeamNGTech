param(
    [Parameter(Position = 0)]
    [ValidateSet(
        'help','setup','install-app',
        'run','drive','run-neural','neural',
        'collect','train',
        'status','doctor',
        'logs','tail-state',
        'config-show','mode','speed',
        'update','register-command'
    )]
    [string]$Command = 'help',

    [double]$TargetSpeed,
    [switch]$DebugView,
    [int]$Epochs = 30,
    [int]$BatchSize = 32,
    [switch]$RecreateVenv,
    [string]$Value,
    [int]$Lines = 40
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$configPath = Join-Path $repoRoot 'config.py'
$logsPath = Join-Path $repoRoot 'logs'
$statePath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\logs\acdriver_state.json'
$appPath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\apps\python\ACDriverApp\ACDriverApp.py'

function Show-Header([string]$text) {
    Write-Host ""
    Write-Host "=== $text ==="
}

function Replace-ConfigLine([string]$pattern, [string]$replacement, [string]$label) {
    if (-not (Test-Path $configPath)) {
        throw "config.py not found at $configPath"
    }
    $raw = Get-Content $configPath -Raw
    $updated = [regex]::Replace($raw, $pattern, $replacement, 1)
    if ($updated -eq $raw) {
        throw "Could not update $label in config.py"
    }
    Set-Content -Path $configPath -Value $updated -NoNewline
    Write-Host "[autoac] Updated $label"
}

function Show-Status {
    Write-Host "User              : $env:USERNAME"
    Write-Host "User profile      : $env:USERPROFILE"
    Write-Host "Repo root         : $repoRoot"
    Write-Host "Python available  : $([bool](Get-Command python -ErrorAction SilentlyContinue))"
    Write-Host "Git available     : $([bool](Get-Command git -ErrorAction SilentlyContinue))"
    Write-Host "AC app exists     : $(Test-Path $appPath)"
    Write-Host "State file exists : $(Test-Path $statePath)"
    Write-Host "Logs folder exists: $(Test-Path $logsPath)"
}

function Run-Doctor {
    Show-Header "AUTOAC DOCTOR"
    Show-Status
    Write-Host ""
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "[doctor] Python missing. Run: autoac setup"
    }
    if (-not (Test-Path (Join-Path $repoRoot '.venv\Scripts\Activate.ps1'))) {
        Write-Host "[doctor] .venv missing. Run: autoac setup"
    }
    if (-not (Test-Path $appPath)) {
        Write-Host "[doctor] AC app missing. Run: autoac install-app"
    }
    if (-not (Test-Path $statePath)) {
        Write-Host "[doctor] Telemetry file not found yet. Start AC and drive briefly."
    }
    Write-Host "[doctor] Done."
}

switch ($Command) {
    'help' {
        Show-Header "AUTOAC HELP"
        Write-Host 'Setup & install:'
        Write-Host '  autoac setup                      # install Python (if needed), create venv, install deps'
        Write-Host '  autoac install-app                # copy AC app into Documents\Assetto Corsa\apps\python'
        Write-Host '  autoac register-command           # register global autoac command in PowerShell profile'
        Write-Host ''
        Write-Host 'Run:'
        Write-Host '  autoac run -DebugView            # run classical mode'
        Write-Host '  autoac drive -DebugView          # alias for run'
        Write-Host '  autoac run-neural -DebugView     # run neural mode'
        Write-Host '  autoac neural -DebugView         # alias for run-neural'
        Write-Host ''
        Write-Host 'Training:'
        Write-Host '  autoac collect                   # collect data'
        Write-Host '  autoac train -Epochs 30 -BatchSize 32'
        Write-Host ''
        Write-Host 'Config helpers:'
        Write-Host '  autoac config-show               # print key config values'
        Write-Host '  autoac mode -Value keys          # set control mode to keys|vjoy'
        Write-Host '  autoac speed -TargetSpeed 70     # set target speed in config.py'
        Write-Host ''
        Write-Host 'Diagnostics:'
        Write-Host '  autoac status                    # show detected paths and files'
        Write-Host '  autoac doctor                    # run setup diagnostics'
        Write-Host '  autoac logs                      # open logs folder in Explorer'
        Write-Host '  autoac tail-state -Lines 40      # watch telemetry json updates'
        Write-Host ''
        Write-Host 'Maintenance:'
        Write-Host '  autoac update                    # git pull latest changes'
        break
    }
    'setup' {
        $args = @()
        if ($RecreateVenv) { $args += '-RecreateVenv' }
        & .\scripts\setup_windows.ps1 @args
        break
    }
    'install-app' {
        & .\scripts\install_ac_app.ps1
        break
    }
    'run' {
        $args = @()
        if ($DebugView) { $args += '-DebugView' }
        if ($PSBoundParameters.ContainsKey('TargetSpeed')) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_classical.ps1 @args
        break
    }
    'drive' {
        $args = @()
        if ($DebugView) { $args += '-DebugView' }
        if ($PSBoundParameters.ContainsKey('TargetSpeed')) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_classical.ps1 @args
        break
    }
    'run-neural' {
        $args = @()
        if ($DebugView) { $args += '-DebugView' }
        if ($PSBoundParameters.ContainsKey('TargetSpeed')) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_neural.ps1 @args
        break
    }
    'neural' {
        $args = @()
        if ($DebugView) { $args += '-DebugView' }
        if ($PSBoundParameters.ContainsKey('TargetSpeed')) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_neural.ps1 @args
        break
    }
    'collect' {
        & .\scripts\collect_data.ps1
        break
    }
    'train' {
        & .\scripts\train_model.ps1 -Epochs $Epochs -BatchSize $BatchSize
        break
    }
    'status' {
        Show-Status
        break
    }
    'doctor' {
        Run-Doctor
        break
    }
    'logs' {
        if (-not (Test-Path $logsPath)) {
            New-Item -ItemType Directory -Force $logsPath | Out-Null
        }
        Start-Process explorer.exe $logsPath
        break
    }
    'tail-state' {
        Show-Header "Telemetry tail"
        Write-Host "Path: $statePath"
        if (-not (Test-Path $statePath)) {
            Write-Host "State file not found yet. Start AC and drive briefly first."
            break
        }
        Get-Content -Path $statePath -Tail $Lines -Wait
        break
    }
    'config-show' {
        if (-not (Test-Path $configPath)) {
            throw "config.py not found"
        }
        Show-Header "Config values"
        $lines = Get-Content $configPath
        $lines | Where-Object {
            $_ -match 'mode:\s*str\s*=|target_kph:\s*float\s*=|monitor_region:\s*Tuple\[int, int, int, int\]\s*='
        } | ForEach-Object { Write-Host $_ }
        break
    }
    'mode' {
        if (-not $Value) {
            throw "Provide mode value. Example: autoac mode -Value keys"
        }
        if ($Value -notin @('keys','vjoy')) {
            throw "Invalid mode '$Value'. Allowed: keys, vjoy"
        }
        Replace-ConfigLine 'mode:\s*str\s*=\s*"[^"]+"' ("mode: str = `"{0}`"" -f $Value) 'control mode'
        break
    }
    'speed' {
        if (-not $PSBoundParameters.ContainsKey('TargetSpeed')) {
            throw "Provide speed. Example: autoac speed -TargetSpeed 70"
        }
        Replace-ConfigLine 'target_kph:\s*float\s*=\s*[0-9]+(\.[0-9]+)?' ("target_kph: float = {0}" -f $TargetSpeed) 'target speed'
        break
    }
    'update' {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw "git not found"
        }
        git -C $repoRoot pull
        break
    }
    'register-command' {
        & .\scripts\register_autoac_command.ps1
        break
    }
}
