param(
    [Parameter(Position = 0)]
    [ValidateSet('help','setup','install-app','run','run-neural','collect','train','status','register-command')]
    [string]$Command = 'help',

    [double]$TargetSpeed,
    [switch]$Debug,
    [int]$Epochs = 30,
    [int]$BatchSize = 32,
    [switch]$RecreateVenv
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

switch ($Command) {
    'help' {
        Write-Host 'autoac commands:'
        Write-Host '  autoac setup                  # create venv + install deps'
        Write-Host '  autoac install-app            # copy AC app into Documents'
        Write-Host '  autoac run -Debug             # run classical mode'
        Write-Host '  autoac run-neural -Debug      # run neural mode'
        Write-Host '  autoac collect                # collect training data'
        Write-Host '  autoac train -Epochs 30       # train model'
        Write-Host '  autoac status                 # show paths for current user'
        Write-Host '  autoac register-command       # install global autoac function'
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
        if ($Debug) { $args += '-DebugView' }
        if ($PSBoundParameters.ContainsKey('TargetSpeed')) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_classical.ps1 @args
        break
    }
    'run-neural' {
        $args = @()
        if ($Debug) { $args += '-DebugView' }
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
        $appPath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\apps\python\ACDriverApp\ACDriverApp.py'
        $statePath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\logs\acdriver_state.json'
        Write-Host "User           : $env:USERNAME"
        Write-Host "User profile   : $env:USERPROFILE"
        Write-Host "Repo root      : $repoRoot"
        Write-Host "AC app exists  : $(Test-Path $appPath)"
        Write-Host "State file seen: $(Test-Path $statePath)"
        break
    }
    'register-command' {
        & .\scripts\register_autoac_command.ps1
        break
    }
}
