Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Watching gpt-5.5 run_tasks/auto_solve. o3 will start after they finish."
while ($true) {
    $running = Get-CimInstance Win32_Process | Where-Object {
        ($_.CommandLine -match 'run_final1154_gpt55_full_floor\.ps1' -or
         $_.CommandLine -match '--model gpt-5\.5' -or
         $_.CommandLine -match '-M gpt-5\.5')
    }
    if (-not $running) {
        break
    }
    Write-Host ("Still waiting for gpt-5.5. running_processes={0} time={1}" -f @($running).Count, (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    Start-Sleep -Seconds 60
}

Write-Host "gpt-5.5 appears finished. Starting o3."
& "$Root\scripts\run_final1154_o3_full_floor.ps1"
