[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# Parse CLI args manually for reliable behavior across wrappers.
$allowedCommands = @(
    'help','setup','install-app',
    'run','drive','run-neural','neural',
    'collect','train',
    'status','doctor',
    'logs','tail-state',
    'config-show','mode','speed',
    'update','register-command'
)

$Command = 'help'
$TargetSpeed = $null
$Ui = $false
$Epochs = 30
$BatchSize = 32
$RecreateVenv = $false
$Value = $null
$Lines = 40

$tokens = @($CliArgs)
if ($tokens.Count -gt 0 -and -not $tokens[0].StartsWith('-')) {
    $Command = $tokens[0].ToLowerInvariant()
    $tokens = if ($tokens.Count -gt 1) { @($tokens[1..($tokens.Count - 1)]) } else { @() }
}
if ($tokens -is [string]) {
    $tokens = @($tokens)
}

# Some launcher paths can split switch tokens into '-' + 'Name'. Recombine.
$normalized = @()
for ($j = 0; $j -lt $tokens.Count; $j++) {
    if ($tokens[$j] -eq '-' -and $j + 1 -lt $tokens.Count) {
        $normalized += ,('-' + $tokens[$j + 1])
        $j++
    } else {
        $normalized += ,$tokens[$j]
    }
}
$tokens = $normalized
if ($tokens -is [string]) {
    $tokens = @($tokens)
}

for ($i = 0; $i -lt $tokens.Count; $i++) {
    $t = $tokens[$i]
    switch -Regex ($t) {
        '^-$' { $Ui = $true; continue }  # fallback when launcher strips switch names
        '^(-)?(Ui|Debug|DebugView)$' { $Ui = $true; continue }
        '^(-)?RecreateVenv$' { $RecreateVenv = $true; continue }
        '^-TargetSpeed$' {
            if ($i + 1 -ge $tokens.Count) { throw 'Missing value for -TargetSpeed' }
            $i++
            $TargetSpeed = [double]$tokens[$i]
            continue
        }
        '^-Epochs$' {
            if ($i + 1 -ge $tokens.Count) { throw 'Missing value for -Epochs' }
            $i++
            $Epochs = [int]$tokens[$i]
            continue
        }
        '^-BatchSize$' {
            if ($i + 1 -ge $tokens.Count) { throw 'Missing value for -BatchSize' }
            $i++
            $BatchSize = [int]$tokens[$i]
            continue
        }
        '^-Value$' {
            if ($i + 1 -ge $tokens.Count) { throw 'Missing value for -Value' }
            $i++
            $Value = $tokens[$i]
            continue
        }
        '^-Lines$' {
            if ($i + 1 -ge $tokens.Count) { throw 'Missing value for -Lines' }
            $i++
            $Lines = [int]$tokens[$i]
            continue
        }
        default {
            throw "Unknown argument: $t (run 'autoac help')"
        }
    }
}

if ($allowedCommands -notcontains $Command) {
    throw "Unknown command '$Command' (run 'autoac help')"
}

$configPath = Join-Path $repoRoot 'config.py'
$logsPath = Join-Path $repoRoot 'logs'
$statePath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\logs\acdriver_state.json'
$controlsIniPath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\cfg\controls.ini'

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
$gameAppPath = if ($gameRoot) {
    Join-Path $gameRoot 'apps\python\ACDriverApp\ACDriverApp.py'
} else {
    $null
}
$documentsAppPath = Join-Path $env:USERPROFILE 'Documents\Assetto Corsa\apps\python\ACDriverApp\ACDriverApp.py'

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
    $gameAppExists = if ($gameAppPath) { Test-Path $gameAppPath } else { $false }
    $documentsAppExists = Test-Path $documentsAppPath
    $gameRootText = if ([string]::IsNullOrWhiteSpace($gameRoot)) { '<not detected>' } else { $gameRoot }
    $stateExists = Test-Path $statePath
    $stateAgeSec = $null
    $stateFresh = $false
    if ($stateExists) {
        $stateAgeSec = [int]((Get-Date) - (Get-Item $statePath).LastWriteTime).TotalSeconds
        $stateFresh = $stateAgeSec -le 2
    }

    Write-Host "User              : $env:USERNAME"
    Write-Host "User profile      : $env:USERPROFILE"
    Write-Host "Repo root         : $repoRoot"
    Write-Host "AC game root      : $gameRootText"
    Write-Host "Python available  : $([bool](Get-Command python -ErrorAction SilentlyContinue))"
    Write-Host "Git available     : $([bool](Get-Command git -ErrorAction SilentlyContinue))"
    Write-Host "AC app in game dir: $gameAppExists"
    Write-Host "AC app in Documents: $documentsAppExists"
    Write-Host "State file exists : $stateExists"
    if ($stateExists) {
        Write-Host "State fresh (<=2s): $stateFresh"
        Write-Host "State age seconds : $stateAgeSec"
    }
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
    $hasGameInstall = if ($gameAppPath) { Test-Path $gameAppPath } else { $false }
    if (-not $hasGameInstall) {
        Write-Host "[doctor] AC app not found in game folder. Run: autoac install-app"
        if (-not $gameRoot) {
            Write-Host "[doctor] Could not detect Assetto Corsa install path automatically."
        }
    }
    if (-not (Test-Path $statePath)) {
        Write-Host "[doctor] Telemetry file not found yet. Start AC and drive briefly."
    } else {
        $ageSec = [int]((Get-Date) - (Get-Item $statePath).LastWriteTime).TotalSeconds
        if ($ageSec -gt 2) {
            Write-Host "[doctor] Telemetry file is stale (${ageSec}s old). Enter a live driving session."
        }
    }
    if (Test-Path $controlsIniPath) {
        $controlsRaw = Get-Content $controlsIniPath -Raw
        if ($controlsRaw -match 'COMBINE_WITH_KEYBOARD_CONTROL=0') {
            Write-Host "[doctor] AC keyboard combine is OFF in controls.ini. Keyboard bot input may be ignored."
            Write-Host "[doctor] Run any drive command (autoac run/drive/neural) and it will auto-fix this."
        }
        if ($controlsRaw -match 'INPUT_METHOD=X360|INPUT_METHOD=WHEEL') {
            Write-Host "[doctor] AC input method is not KEYBOARD in controls.ini. Keyboard bot input may be ignored."
        }
    }
    Write-Host "[doctor] Done."
}

function Ensure-AcKeyboardControl {
    if (-not (Test-Path $controlsIniPath)) {
        return
    }

    $raw = Get-Content $controlsIniPath -Raw
    $updated = $raw
    $changedInputMethod = $false
    $updated = [regex]::Replace($updated, 'COMBINE_WITH_KEYBOARD_CONTROL=0', 'COMBINE_WITH_KEYBOARD_CONTROL=1')
    if ($updated -match '(?m)^INPUT_METHOD=(?!KEYBOARD).*$') {
        $changedInputMethod = $true
    }
    $updated = [regex]::Replace($updated, '(?m)^INPUT_METHOD=.*$', 'INPUT_METHOD=KEYBOARD')

    if ($updated -ne $raw) {
        Set-Content -Path $controlsIniPath -Value $updated -NoNewline
        Write-Host "[autoac] Updated controls.ini for keyboard bot input (INPUT_METHOD=KEYBOARD, COMBINE_WITH_KEYBOARD_CONTROL=1)"
        if ($changedInputMethod) {
            $acRunning = Get-Process -Name AssettoCorsa -ErrorAction SilentlyContinue
            if ($acRunning) {
                Write-Host "[autoac] Restart Assetto Corsa once so INPUT_METHOD change is applied."
            }
        }
    }
}

switch ($Command) {
    'help' {
        Show-Header "AUTOAC HELP"
        Write-Host 'Setup & install:'
        Write-Host '  autoac setup                      # install Python (if needed), create venv, install deps'
        Write-Host '  autoac setup recreatevenv         # recreate .venv from scratch'
        Write-Host '  autoac install-app                # copy AC app into AC game apps\python (and Documents fallback)'
        Write-Host '  autoac register-command           # register global autoac command in PowerShell profile'
        Write-Host ''
        Write-Host 'Run:'
        Write-Host '  autoac run ui                    # run classical mode + debug window'
        Write-Host '  autoac drive ui                  # alias for run'
        Write-Host '  autoac run-neural ui             # run neural mode + debug window'
        Write-Host '  autoac neural ui                 # alias for run-neural'
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
        Ensure-AcKeyboardControl
        $args = @()
        if ($Ui) { $args += '-DebugView' }
        if ($null -ne $TargetSpeed) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_classical.ps1 @args
        break
    }
    'drive' {
        Ensure-AcKeyboardControl
        $args = @()
        if ($Ui) { $args += '-DebugView' }
        if ($null -ne $TargetSpeed) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_classical.ps1 @args
        break
    }
    'run-neural' {
        Ensure-AcKeyboardControl
        $args = @()
        if ($Ui) { $args += '-DebugView' }
        if ($null -ne $TargetSpeed) { $args += @('-TargetSpeed', $TargetSpeed) }
        & .\scripts\run_neural.ps1 @args
        break
    }
    'neural' {
        Ensure-AcKeyboardControl
        $args = @()
        if ($Ui) { $args += '-DebugView' }
        if ($null -ne $TargetSpeed) { $args += @('-TargetSpeed', $TargetSpeed) }
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
        if ($null -eq $TargetSpeed) {
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
