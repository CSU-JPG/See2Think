Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-WrongRenderProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match 'vaot_wrong_render' -and
        ($_.CommandLine -match 'run_tasks.py|auto_solve.py') -and
        $_.ProcessId -ne $PID
    }
}

function Start-Retry {
    param(
        [string]$Name,
        [string]$Model,
        [string]$RequestModel,
        [string]$Tasks,
        [int]$Workers
    )
    $safe = $Model -replace ":", "-" -replace "/", "_" -replace "\\", "_"
    $outRoot = "$Root\newtasks\final600_${safe}_vaot_wrong_render_floor"
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $out = "$Root\newlogs\retry_wrong_render_${Name}_$ts.out"
    $err = "$Root\newlogs\retry_wrong_render_${Name}_$ts.err"
    $cmd = @"
`$env:WR_MODEL='$Model'
`$env:WR_REQUEST_MODEL='$RequestModel'
`$env:WR_TASKS='$Tasks'
`$env:WR_OUTPUT_ROOT='$outRoot'
`$env:WORKERS='$Workers'
& '$Root\scripts\run_final600_wrong_render_one.ps1'
"@
    $p = Start-Process powershell `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd)
    Write-Host "RETRY_STARTED $Name pid=$($p.Id) tasks=$Tasks workers=$Workers"
    Write-Host "  stdout=$out"
    Write-Host "  stderr=$err"
}

New-Item -ItemType Directory -Force "$Root\newlogs" | Out-Null

Write-Host "WAIT current wrong_render runs to finish..."
while ($true) {
    $procs = @(Get-WrongRenderProcesses)
    if ($procs.Count -eq 0) {
        break
    }
    $sample = ($procs | Select-Object -First 6 | ForEach-Object { [string]$_.ProcessId }) -join ","
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') still running: $($procs.Count) processes [$sample]"
    Start-Sleep -Seconds 300
}

Write-Host "Current wrong_render runs finished. Re-assembling..."
python scripts\assemble_final_results.py --settings text_only no_render wrong_render --overwrite
python scripts\write_final_results_overview.py

Write-Host "Export missing wrong_render retry JSON..."
python scripts\export_missing_tasks_from_final_results.py --setting wrong_render --model gpt-5.5
python scripts\export_missing_tasks_from_final_results.py --setting wrong_render --model o3
python scripts\export_missing_tasks_from_final_results.py --setting wrong_render --model gemini-3.5-flash

Start-Retry `
    -Name "gpt55" `
    -Model "gpt-5.5" `
    -RequestModel "gpt-5.5:floor" `
    -Tasks "json/run_tasks_need_600_retry/gpt-5.5__wrong_render__missing_final_results.json" `
    -Workers 2

Start-Retry `
    -Name "o3" `
    -Model "o3" `
    -RequestModel "o3:floor" `
    -Tasks "json/run_tasks_need_600_retry/o3__wrong_render__missing_final_results.json" `
    -Workers 3

Start-Retry `
    -Name "gemini35" `
    -Model "gemini-3.5-flash" `
    -RequestModel "gemini-3.5-flash:floor" `
    -Tasks "json/run_tasks_need_600_retry/gemini-3.5-flash__wrong_render__missing_final_results.json" `
    -Workers 2

Write-Host "Retry-once jobs launched."
