param(
    [int]$PollMinutes = 60,
    [int]$RetryWorkers = 2,
    [string]$Model = "qwen3-vl-32b-instruct",
    [string]$RequestModel = "qwen3-vl-32b-instruct",
    [string]$AccEvalScript = "",
    [string]$RetryScript = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

# This script should be placed in <project>\scripts\.
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ([string]::IsNullOrWhiteSpace($AccEvalScript)) {
    $AccEvalScript = Join-Path $Root "scripts\start_qwen3vl32b_acc_and_eval_1200.ps1"
}
if ([string]::IsNullOrWhiteSpace($RetryScript)) {
    $RetryScript = Join-Path $Root "scripts\start_qwen3vl32b_setting_api.ps1"
}

$TasksFile = Join-Path $Root "json\tasks_see2thinkbench_1200task_available.json"
$StatusBuilder = Join-Path $Root "scripts\build_qwen_failed_task_lists.py"
$WatcherLogDir = Join-Path $Root "newlogs\qwen3vl32b_auto_watch"
$StartedMarker = Join-Path $WatcherLogDir "acc_eval_started.marker"
$WatcherLog = Join-Path $WatcherLogDir "watcher.log"

New-Item -ItemType Directory -Force $WatcherLogDir | Out-Null

function Write-WatcherLog {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message"
    Write-Host $line
    Add-Content -LiteralPath $WatcherLog -Value $line -Encoding UTF8
}

function Get-GenerationProcesses {
    return @(
        Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -eq "python.exe" -and
            $_.CommandLine -match "run_tasks.py|auto_solve.py" -and
            $_.CommandLine -match [regex]::Escape($Model)
        }
    )
}

function Get-AccEvalProcesses {
    return @(
        Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -eq "python.exe" -and
            $_.CommandLine -match "answer_judge.py|key_step_metric_judge.py" -and
            $_.CommandLine -match "qwen3vl32b|qwen3-vl-32b-instruct"
        }
    )
}

function Build-And-ReadStatus {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $statusDir = Join-Path $Root "newlogs\qwen3vl32b_instruct_status_$ts"

    & python $StatusBuilder `
        --tasks $TasksFile `
        --model $Model `
        --out-dir $statusDir

    if ($LASTEXITCODE -ne 0) {
        throw "Status builder exited with code $LASTEXITCODE"
    }

    $summaryPath = Join-Path $statusDir "summary.csv"
    if (-not (Test-Path -LiteralPath $summaryPath)) {
        throw "summary.csv was not generated: $summaryPath"
    }

    return @{
        Directory = $statusDir
        Rows = @(Import-Csv -LiteralPath $summaryPath)
    }
}

function Start-FailedRetries {
    param(
        [string]$StatusDirectory,
        [array]$Rows
    )

    if (-not (Test-Path -LiteralPath $RetryScript)) {
        throw "Retry startup script not found: $RetryScript"
    }

    $settingMap = @{
        "text_cot"          = "failed_text_cot.json"
        "vaot_no_render"    = "failed_vaot_no_render.json"
        "vaot_full"         = "failed_vaot_full.json"
        "vaot_wrong_render" = "failed_vaot_wrong_render.json"
    }

    $started = 0

    foreach ($setting in $settingMap.Keys) {
        $row = $Rows | Where-Object { $_.setting -eq $setting } | Select-Object -First 1
        if ($null -eq $row) {
            Write-WatcherLog "Cannot retry ${setting}: summary row is missing."
            continue
        }

        $failedCount = [int]$row.failed_or_incomplete
        if ($failedCount -le 0) {
            Write-WatcherLog "$setting is already complete; no retry needed."
            continue
        }

        $failedJson = Join-Path $StatusDirectory $settingMap[$setting]
        if (-not (Test-Path -LiteralPath $failedJson)) {
            Write-WatcherLog "Cannot retry ${setting}: failed-task JSON not found: $failedJson"
            continue
        }

        Write-WatcherLog "Starting retry for ${setting}: $failedCount task(s), workers=$RetryWorkers."

        # The setting launcher itself starts run_tasks.py in the background.
        & powershell.exe `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $RetryScript `
            -Setting $setting `
            -Model $Model `
            -RequestModel $RequestModel `
            -Tasks $failedJson `
            -Workers $RetryWorkers

        if ($LASTEXITCODE -ne 0) {
            Write-WatcherLog "Retry launcher for $setting returned exit code $LASTEXITCODE."
        }
        else {
            $started += 1
            Start-Sleep -Seconds 2
        }
    }

    return $started
}

Write-WatcherLog "Watcher started. Poll interval: $PollMinutes minute(s)."
Write-WatcherLog "Retry workers per setting: $RetryWorkers."
Write-WatcherLog "Project root: $Root"
Write-WatcherLog "Retry script: $RetryScript"
Write-WatcherLog "ACC/Eval script: $AccEvalScript"

while ($true) {
    try {
        $generation = Get-GenerationProcesses

        if ($generation.Count -gt 0) {
            Write-WatcherLog "Generation/retry is still running: $($generation.Count) related process(es)."
            Start-Sleep -Seconds ($PollMinutes * 60)
            continue
        }

        Write-WatcherLog "No generation processes found. Rebuilding completeness status."
        $status = Build-And-ReadStatus
        $rows = $status.Rows

        $expectedSettings = @(
            "text_cot",
            "vaot_no_render",
            "vaot_full",
            "vaot_wrong_render"
        )

        $allGood = $true
        foreach ($setting in $expectedSettings) {
            $row = $rows | Where-Object { $_.setting -eq $setting } | Select-Object -First 1

            if ($null -eq $row) {
                Write-WatcherLog "Missing summary row for $setting."
                $allGood = $false
                continue
            }

            Write-WatcherLog (
                "Status {0}: complete={1}, failed_or_incomplete={2}, total={3}" -f
                $row.setting, $row.complete, $row.failed_or_incomplete, $row.total
            )

            if (
                [int]$row.complete -ne 1200 -or
                [int]$row.failed_or_incomplete -ne 0 -or
                [int]$row.total -ne 1200
            ) {
                $allGood = $false
            }
        }

        if (-not $allGood) {
            Write-WatcherLog "Some settings are incomplete. Starting retries using the latest failed-task JSON files."
            $started = Start-FailedRetries -StatusDirectory $status.Directory -Rows $rows

            if ($started -gt 0) {
                Write-WatcherLog "Started retry jobs for $started setting(s). Next check will occur after $PollMinutes minute(s)."
            }
            else {
                Write-WatcherLog "No retry job was started. Check watcher.log and the latest status directory."
            }

            Start-Sleep -Seconds ($PollMinutes * 60)
            continue
        }

        Write-WatcherLog "All four settings are complete: 1200/1200 with zero failures."

        $existingEval = Get-AccEvalProcesses
        if ($existingEval.Count -gt 0) {
            Write-WatcherLog "ACC/Eval is already running: $($existingEval.Count) process(es). Exiting watcher."
            break
        }

        if (Test-Path -LiteralPath $StartedMarker) {
            Write-WatcherLog "ACC/Eval marker already exists; refusing to launch a duplicate run. Exiting watcher."
            break
        }

        if (-not (Test-Path -LiteralPath $AccEvalScript)) {
            throw "ACC/Eval startup script not found: $AccEvalScript"
        }

        Set-Content -LiteralPath $StartedMarker `
            -Value "$(Get-Date -Format o)`n$AccEvalScript" `
            -Encoding UTF8

        $stdout = Join-Path $WatcherLogDir "acc_eval_launcher.out"
        $stderr = Join-Path $WatcherLogDir "acc_eval_launcher.err"

        $process = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", "`"$AccEvalScript`""
            ) `
            -WorkingDirectory $Root `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru

        Write-WatcherLog "ACC/Eval launcher started. PID=$($process.Id)"
        Write-WatcherLog "Launcher stdout: $stdout"
        Write-WatcherLog "Launcher stderr: $stderr"
        Write-WatcherLog "Watcher completed successfully."
        break
    }
    catch {
        Write-WatcherLog "ERROR: $($_.Exception.Message)"
        Start-Sleep -Seconds ($PollMinutes * 60)
    }
}
