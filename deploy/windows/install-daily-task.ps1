param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$TaskName = "WangDian Inventory Daily",
    [string]$RunAt = "01:10"
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $ProjectRoot "deploy\windows\run-daily-job.ps1"
if (-not (Test-Path $Runner)) {
    throw "Daily task runner was not found: $Runner"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -ProjectRoot `"$ProjectRoot`""
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunAt
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Synchronize yesterday's WangDian data and export the daily report." `
    -Force

Write-Host "Scheduled task installed: $TaskName at $RunAt"
