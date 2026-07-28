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
    throw "OPENAI_API_KEY is missing. Put it in config.sh or set `$env:OPENAI_API_KEY first."
}
if (-not $env:OPENAI_BASE_URL) {
    $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = "gemini-3.5-flash:floor"
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
$env:SEE2THINK_OUTPUT_BASE = "$Root\newtasks\final1154_gemini-3.5-flash_vaot_full_floor"
$StartPos = if ($env:START_POS) { [int]$env:START_POS } else { 416 }
$EndPos = if ($env:END_POS) { [int]$env:END_POS } else { 1154 }

$env:SEE2THINK_LOG_DIR = "$Root\newlogs\final1154_gemini-3.5-flash_vaot_full_floor_continue_${StartPos}_${EndPos}"

New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

python -u solve/run_tasks.py `
  --tasks json/tasks_see2thinkbench_1154task_available.json `
  --mode banana `
  --model gemini-3.5-flash `
  --workers 1 `
  --start $StartPos `
  --end $EndPos `
  --linear `
  --setting vaot_full `
  --prompt_dir newprompt
