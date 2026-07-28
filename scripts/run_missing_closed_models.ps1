Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Import-ConfigSh {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "config.sh not found: $Path"
    }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
            $name = $Matches[1]
            $value = ($Matches[2] -replace '\s+#.*$', '').Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Count-Tasks {
    param([string]$Tasks)
    return [int](python -c "import json; print(len(json.load(open(r'$Tasks', encoding='utf-8'))))")
}

function Run-Missing {
    param(
        [string]$Model,
        [string]$RequestModel,
        [string]$Setting,
        [string]$RunSetting,
        [string]$OutputBase,
        [int]$Workers
    )

    python scripts/export_missing_tasks_from_final_results.py --setting $Setting --model $Model
    $SafeModel = $Model -replace ":", "-"
    $Tasks = "json/run_tasks_need_600_retry/${SafeModel}__${Setting}__missing_final_results.json"
    $TaskCount = Count-Tasks $Tasks
    if ($TaskCount -le 0) {
        Write-Host "SKIP ${Model} ${Setting}: no missing tasks"
        return
    }

    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $env:SKIP_CONFIRM = "1"
    $env:SEE2THINK_DATA_BASE = $Root
    $env:SEE2THINK_LLM_BACKEND = "openai"
    $env:SEE2THINK_REQUEST_MODEL = $RequestModel
    $env:SEE2THINK_TASK_TIMEOUT_SECONDS = if ($env:SEE2THINK_TASK_TIMEOUT_SECONDS) { $env:SEE2THINK_TASK_TIMEOUT_SECONDS } else { "1200" }
    $env:SEE2THINK_OUTPUT_BASE = $OutputBase
    $env:SEE2THINK_LOG_DIR = "$Root\newlogs\retry_missing_${SafeModel}_${Setting}_${ts}"

    New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
    New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

    Write-Host "============================================================"
    Write-Host "RETRY model=$Model setting=$Setting run_setting=$RunSetting tasks=$TaskCount workers=$Workers"
    Write-Host "tasks=$Tasks"
    Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
    Write-Host "logs=$env:SEE2THINK_LOG_DIR"
    Write-Host "============================================================"

    python -u solve/run_tasks.py `
      --tasks $Tasks `
      --mode banana `
      --model $Model `
      --workers $Workers `
      --start 0 `
      --end $TaskCount `
      --setting $RunSetting `
      --prompt_dir newprompt

    if ($LASTEXITCODE -ne 0) {
        throw "run_tasks.py failed for $Model $Setting with exit code $LASTEXITCODE"
    }
}

Import-ConfigSh "$Root\config.sh"
if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
    $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

$models = @(
    @{ Model = "gpt-5.5"; Request = "gpt-5.5:floor"; Workers = 2 },
    @{ Model = "o3"; Request = "o3:floor"; Workers = 2 },
    @{ Model = "gemini-3.5-flash"; Request = "gemini-3.5-flash:floor"; Workers = 2 }
)

$settings = @(
    @{ Name = "full"; Run = "vaot_full"; Output = "final1200_{model}_vaot_full_floor" },
    @{ Name = "text_only"; Run = "text_cot"; Output = "final600_{model}_text_cot" },
    @{ Name = "no_render"; Run = "vaot_no_render"; Output = "final600_{model}_vaot_no_render" },
    @{ Name = "wrong_render"; Run = "vaot_wrong_render"; Output = "final600_{model}_vaot_wrong_render_floor" }
)

foreach ($m in $models) {
    $safe = $m.Model -replace ":", "-"
    foreach ($s in $settings) {
        $outName = $s.Output.Replace("{model}", $safe)
        Run-Missing `
            -Model $m.Model `
            -RequestModel $m.Request `
            -Setting $s.Name `
            -RunSetting $s.Run `
            -OutputBase "$Root\newtasks\$outName" `
            -Workers $m.Workers
    }
}

Write-Host "Reassembling final results..."
python scripts/assemble_final_results.py --settings full text_only no_render wrong_render --models gpt-5.5 o3 gemini-3.5-flash:stable --overwrite
python scripts/write_final_results_overview.py
