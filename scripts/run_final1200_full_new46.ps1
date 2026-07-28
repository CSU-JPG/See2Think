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

function Run-FullNew46 {
    param(
        [string]$Model,
        [string]$RequestModel,
        [int]$StartPos,
        [int]$EndPos,
        [int]$Workers
    )

    $env:SKIP_CONFIRM = "1"
    $env:SEE2THINK_DATA_BASE = $Root
    $env:SEE2THINK_LLM_BACKEND = "openai"
    $env:SEE2THINK_REQUEST_MODEL = $RequestModel
    $env:SEE2THINK_TASK_TIMEOUT_SECONDS = if ($env:SEE2THINK_TASK_TIMEOUT_SECONDS) { $env:SEE2THINK_TASK_TIMEOUT_SECONDS } else { "1200" }
    $env:SEE2THINK_OUTPUT_BASE = "$Root\newtasks\final1200_${Model}_vaot_full_floor"
    $env:SEE2THINK_LOG_DIR = "$Root\newlogs\final1200_${Model}_vaot_full_floor_${StartPos}_${EndPos}"

    New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
    New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

    Write-Host "============================================================"
    Write-Host "START $Model request=$RequestModel range=$StartPos..$EndPos workers=$Workers"
    Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
    Write-Host "logs=$env:SEE2THINK_LOG_DIR"
    Write-Host "============================================================"

    python -u solve/run_tasks.py `
      --tasks json/tasks_see2thinkbench_1200task_available.json `
      --mode banana `
      --model $Model `
      --workers $Workers `
      --start $StartPos `
      --end $EndPos `
      --linear `
      --setting vaot_full `
      --prompt_dir newprompt

    if ($LASTEXITCODE -ne 0) {
        throw "run_tasks.py failed for $Model with exit code $LASTEXITCODE"
    }
}

Import-ConfigSh "$Root\config.sh"

if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
    $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

$StartPos = if ($env:START_POS) { [int]$env:START_POS } else { 1154 }
$EndPos = if ($env:END_POS) { [int]$env:END_POS } else { 1200 }
$Workers = if ($env:WORKERS) { [int]$env:WORKERS } else { 1 }
$ModelList = if ($env:FULL_MODELS) {
    $env:FULL_MODELS.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
} else {
    @("gemini-3.5-flash", "o3", "gpt-5.5")
}

foreach ($Model in $ModelList) {
    switch ($Model) {
        "gemini-3.5-flash" { Run-FullNew46 -Model $Model -RequestModel "gemini-3.5-flash:floor" -StartPos $StartPos -EndPos $EndPos -Workers $Workers }
        "o3" { Run-FullNew46 -Model $Model -RequestModel "o3:floor" -StartPos $StartPos -EndPos $EndPos -Workers $Workers }
        "gpt-5.5" { Run-FullNew46 -Model $Model -RequestModel "gpt-5.5:floor" -StartPos $StartPos -EndPos $EndPos -Workers $Workers }
        default { throw "Unsupported FULL_MODELS entry: $Model" }
    }
}
