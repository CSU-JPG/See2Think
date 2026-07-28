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

Import-ConfigSh "$Root\config.sh"

if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
    $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

$OutputRoot = "$Root\newtasks\final1154_o3_vaot_full_floor"
$DefaultStart = python scripts/find_next_start.py `
  --tasks json/tasks_see2thinkbench_1154task_available.json `
  --output-root $OutputRoot `
  --subdir banana_o3_vaot_full `
  --require-render

$StartPos = if ($env:O3_START_POS) { [int]$env:O3_START_POS } else { [int]$DefaultStart }
$EndPos = if ($env:END_POS) { [int]$env:END_POS } else { 1154 }
$Workers = if ($env:WORKERS) { [int]$env:WORKERS } else { 1 }

$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = "o3:floor"
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
$env:SEE2THINK_OUTPUT_BASE = $OutputRoot
$env:SEE2THINK_LOG_DIR = "$Root\newlogs\final1154_o3_vaot_full_floor_${StartPos}_${EndPos}"

New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

Write-Host "============================================================"
Write-Host "START o3 request=o3:floor range=$StartPos..$EndPos workers=$Workers"
Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
Write-Host "logs=$env:SEE2THINK_LOG_DIR"
Write-Host "============================================================"

python -u solve/run_tasks.py `
  --tasks json/tasks_see2thinkbench_1154task_available.json `
  --mode banana `
  --model o3 `
  --workers $Workers `
  --start $StartPos `
  --end $EndPos `
  --setting vaot_full `
  --prompt_dir prompt
