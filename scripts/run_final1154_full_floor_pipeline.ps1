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

function Run-Full {
    param(
        [string]$Model,
        [string]$RequestModel,
        [int]$StartPos,
        [int]$EndPos
    )

    $env:SKIP_CONFIRM = "1"
    $env:SEE2THINK_DATA_BASE = $Root
    $env:SEE2THINK_LLM_BACKEND = "openai"
    $env:SEE2THINK_REQUEST_MODEL = $RequestModel
    $env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
    $env:SEE2THINK_OUTPUT_BASE = "$Root\newtasks\final1154_${Model}_vaot_full_floor"
    $env:SEE2THINK_LOG_DIR = "$Root\newlogs\final1154_${Model}_vaot_full_floor_${StartPos}_${EndPos}"

    New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
    New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

    $startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "============================================================"
    Write-Host "START $Model request=$RequestModel range=$StartPos..$EndPos at $startedAt"
    Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
    Write-Host "logs=$env:SEE2THINK_LOG_DIR"
    Write-Host "============================================================"

    python -u solve/run_tasks.py `
      --tasks json/tasks_see2thinkbench_1154task_available.json `
      --mode banana `
      --model $Model `
      --workers 1 `
      --start $StartPos `
      --end $EndPos `
      --linear `
      --setting vaot_full `
      --prompt_dir newprompt

    $endedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "END $Model at $endedAt"
}

Import-ConfigSh "$Root\config.sh"

if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
    $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

$GeminiStart = if ($env:GEMINI_START_POS) { [int]$env:GEMINI_START_POS } else { 865 }
$O3Start = if ($env:O3_START_POS) { [int]$env:O3_START_POS } else { 0 }
$Gpt55Start = if ($env:GPT55_START_POS) { [int]$env:GPT55_START_POS } else { 0 }
$EndPos = if ($env:END_POS) { [int]$env:END_POS } else { 1154 }

Run-Full -Model "gemini-3.5-flash" -RequestModel "gemini-3.5-flash:floor" -StartPos $GeminiStart -EndPos $EndPos

if ($env:RUN_AFTER_GEMINI -notin @("1", "true", "True")) {
    Write-Host "RUN_AFTER_GEMINI is not set; stopping pipeline before o3/gpt-5.5 to avoid expensive image routing."
    exit 0
}

Run-Full -Model "o3" -RequestModel "o3:floor" -StartPos $O3Start -EndPos $EndPos
Run-Full -Model "gpt-5.5" -RequestModel "gpt-5.5:floor" -StartPos $Gpt55Start -EndPos $EndPos
