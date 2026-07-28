Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Watching current full runs. wrong_render closed-source pipeline starts after full gpt-5.5/o3 finish."
while ($true) {
    $running = Get-CimInstance Win32_Process | Where-Object {
        ($_.CommandLine -match '--setting vaot_full' -and
         ($_.CommandLine -match '--model gpt-5\.5' -or $_.CommandLine -match '-M gpt-5\.5' -or
          $_.CommandLine -match '--model o3' -or $_.CommandLine -match '-M o3'))
    }
    if (-not $running) {
        break
    }
    Write-Host ("Still waiting for full runs. running_processes={0} time={1}" -f @($running).Count, (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    Start-Sleep -Seconds 300
}

Write-Host "Full runs appear finished. Starting closed-source wrong_render parallel pipeline."
& "$Root\scripts\start_closed_wrong_render_parallel.ps1"
