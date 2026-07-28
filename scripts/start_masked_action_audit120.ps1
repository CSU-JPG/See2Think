Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
New-Item -ItemType Directory -Force "$Root\newlogs" | Out-Null

python scripts/export_wrong_render_audit_tasks_by_model.py

function Start-MaskedRun {
    param(
        [string]$Name,
        [string]$Model,
        [string]$RequestModel,
        [string]$Tasks,
        [string]$Setting,
        [int]$Workers
    )
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $out = "$Root\newlogs\launcher_masked_${Name}_${Setting}_$ts.out"
    $err = "$Root\newlogs\launcher_masked_${Name}_${Setting}_$ts.err"
    $cmd = @"
`$env:MASK_MODEL='$Model'
`$env:MASK_REQUEST_MODEL='$RequestModel'
`$env:MASK_TASKS='$Tasks'
`$env:MASK_SETTING='$Setting'
`$env:WORKERS='$Workers'
& '$Root\scripts\run_masked_audit_120_one.ps1'
"@
    $p = Start-Process powershell `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err `
        -ArgumentList @("-ExecutionPolicy", "Bypass", "-Command", $cmd)
    Write-Host "$Name $Setting pid=$($p.Id) workers=$Workers stdout=$out"
}

$runs = @(
    @{ Name = "gpt55"; Model = "gpt-5.5"; Request = "gpt-5.5:floor"; Tasks = "json/run_tasks_wrong_render_audit_120/gpt-5.5__wrong_render_audit_120.json"; Workers = 1 },
    @{ Name = "o3"; Model = "o3"; Request = "o3:floor"; Tasks = "json/run_tasks_wrong_render_audit_120/o3__wrong_render_audit_120.json"; Workers = 1 },
    @{ Name = "gemini35"; Model = "gemini-3.5-flash"; Request = "gemini-3.5-flash:floor"; Tasks = "json/run_tasks_wrong_render_audit_120/gemini-3.5-flash__wrong_render_audit_120.json"; Workers = 2 }
)

foreach ($run in $runs) {
    if (Test-Path -LiteralPath $run.Tasks) {
        Start-MaskedRun -Name $run.Name -Model $run.Model -RequestModel $run.Request -Tasks $run.Tasks -Setting "vaot_full" -Workers $run.Workers
        Start-MaskedRun -Name $run.Name -Model $run.Model -RequestModel $run.Request -Tasks $run.Tasks -Setting "vaot_wrong_render" -Workers $run.Workers
    }
}
