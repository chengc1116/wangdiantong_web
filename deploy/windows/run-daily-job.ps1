param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
)

$ErrorActionPreference = "Stop"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDirectory = Join-Path $ProjectRoot "data"
$StandardLog = Join-Path $LogDirectory "daily-sync.log"
$ErrorLog = Join-Path $LogDirectory "daily-sync-error.log"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment was not found: $Python"
}

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

Push-Location $ProjectRoot
try {
    & $Python -m wangdian_inventory.app --daily-job --no-browser 1>> $StandardLog 2>> $ErrorLog
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
