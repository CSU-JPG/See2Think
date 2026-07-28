Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force "$Root\newlogs" | Out-Null

function Start-WrongRender {
    param(
        [string]$Name,
        [string]$Model,
        [string]$RequestModel,
        [string]$Tasks,
        [int]$Workers
    )
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $out = "$Root\newlogs\launcher_wrong_render_${Name}_$ts.out"
    $err = "$Root\newlogs\launcher_wrong_render_${Name}_$ts.err"
    $cmd = @"
`$env:WR_MODEL='$Model'
`$env:WR_REQUEST_MODEL='$RequestModel'
`$env:WR_TASKS='$Tasks'
`$env:WORKERS='$Workers'
& '$Root\scripts\run_final600_wrong_render_one.ps1'
"@
    $p = Start-Process powershell `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err `
        -ArgumentList @("-ExecutionPolicy", "Bypass", "-Command", $cmd)
    Write-Host "$Name pid=$($p.Id) workers=$Workers stdout=$out"
}

Start-WrongRender `
    -Name "gpt55" `
    -Model "gpt-5.5" `
    -RequestModel "gpt-5.5:floor" `
    -Tasks "json/run_tasks_need_600/gpt-5.5__valid_wrong_render_step1__need_590.json" `
    -Workers 2

Start-WrongRender `
    -Name "o3" `
    -Model "o3" `
    -RequestModel "o3:floor" `
    -Tasks "json/run_tasks_need_600/o3__valid_wrong_render_step1__need_534.json" `
    -Workers 3

Start-WrongRender `
    -Name "gemini35" `
    -Model "gemini-3.5-flash" `
    -RequestModel "gemini-3.5-flash:floor" `
    -Tasks "json/run_tasks_need_600/gemini-3.5-flash__valid_wrong_render_step1__need_590.json" `
    -Workers 2
