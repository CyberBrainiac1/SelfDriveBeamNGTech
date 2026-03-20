param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$DebugView = $false
$TargetSpeed = $null

$tokens = @($CliArgs)
if ($tokens -is [string]) { $tokens = @($tokens) }

for ($i = 0; $i -lt $tokens.Count; $i++) {
    $t = $tokens[$i]
    switch -Regex ($t) {
        '^-$' { $DebugView = $true; continue }
        '^(-)?(Ui|Debug|DebugView)$' { $DebugView = $true; continue }
        '^-TargetSpeed$' {
            if ($i + 1 -ge $tokens.Count) { throw 'Missing value for -TargetSpeed' }
            $i++
            $TargetSpeed = [double]$tokens[$i]
            continue
        }
        default { }
    }
}

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$activateScript = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $activateScript)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

& $activateScript

$args = @('.\main.py', '--mode', 'classical')
if ($DebugView) { $args += '--debug' }
if ($null -ne $TargetSpeed) {
    $args += @('--target-speed', "$TargetSpeed")
}

Write-Host "[run-classical] python $($args -join ' ')"
python @args
