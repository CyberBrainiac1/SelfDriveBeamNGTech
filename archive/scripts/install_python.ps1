param(
    [string]$PythonWingetId = "Python.Python.3.11"
)

$ErrorActionPreference = 'Stop'

function Get-PythonExecutable {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $resolved = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($resolved) { return $resolved.Trim() }
        } catch {}
    }

    $candidates = @(
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:LocalAppData\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

$existing = Get-PythonExecutable
if ($existing) {
    Write-Host "[python] Python already installed: $existing"
    return
}

$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    throw "winget is not available. Install Python manually: https://www.python.org/downloads/"
}

Write-Host "[python] Installing Python with winget ($PythonWingetId) ..."
winget install -e --id $PythonWingetId --scope user --accept-package-agreements --accept-source-agreements

$installed = Get-PythonExecutable
if (-not $installed) {
    throw "Python install finished but executable was not detected. Open a new terminal and try again."
}

Write-Host "[python] Installed successfully: $installed"
& $installed --version
