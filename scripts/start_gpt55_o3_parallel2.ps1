Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force "$Root\newlogs" | Out-Null

$env:END_POS = "1154"
$env:WORKERS = "2"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"

$env:GPT55_START_POS = if ($env:GPT55_START_POS) { $env:GPT55_START_POS } else { "305" }
$gptOut = "$Root\newlogs\launcher_gpt55_parallel2_$ts.out"
$gptErr = "$Root\newlogs\launcher_gpt55_parallel2_$ts.err"
$gpt = Start-Process powershell `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $gptOut `
    -RedirectStandardError $gptErr `
    -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", "$Root\scripts\run_final1154_gpt55_full_floor.ps1")

$env:O3_START_POS = if ($env:O3_START_POS) { $env:O3_START_POS } else { "50" }
$o3Out = "$Root\newlogs\launcher_o3_parallel2_$ts.out"
$o3Err = "$Root\newlogs\launcher_o3_parallel2_$ts.err"
$o3 = Start-Process powershell `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $o3Out `
    -RedirectStandardError $o3Err `
    -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", "$Root\scripts\run_final1154_o3_full_floor.ps1")

Write-Host "gpt55_pid=$($gpt.Id) start=$env:GPT55_START_POS workers=$env:WORKERS stdout=$gptOut"
Write-Host "o3_pid=$($o3.Id) start=$env:O3_START_POS workers=$env:WORKERS stdout=$o3Out"
