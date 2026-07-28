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

function Safe-Name {
    param([string]$Name)
    return ($Name -replace ":", "-" -replace "/", "_" -replace "\\", "_")
}

Import-ConfigSh "$Root\config.sh"

if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
    $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

if (-not $env:WR_MODEL) { throw "WR_MODEL is required" }
if (-not $env:WR_REQUEST_MODEL) { throw "WR_REQUEST_MODEL is required" }
if (-not $env:WR_TASKS) { throw "WR_TASKS is required" }

$Model = $env:WR_MODEL
$RequestModel = $env:WR_REQUEST_MODEL
$Tasks = $env:WR_TASKS
$Workers = if ($env:WORKERS) { [int]$env:WORKERS } else { 1 }
$SafeModel = Safe-Name $Model
$OutputRoot = if ($env:WR_OUTPUT_ROOT) { $env:WR_OUTPUT_ROOT } else { "$Root\newtasks\final600_${SafeModel}_vaot_wrong_render_floor" }
$Subdir = "banana_${Model}_vaot_wrong_render"
$DefaultStart = python scripts/find_next_start.py `
  --tasks $Tasks `
  --output-root $OutputRoot `
  --subdir $Subdir `
  --require-render

$StartPos = if ($env:START_POS) { [int]$env:START_POS } else { [int]$DefaultStart }
$EndPos = if ($env:END_POS) { [int]$env:END_POS } else {
    python -c "import json; print(len(json.load(open(r'$Tasks', encoding='utf-8'))))"
}

$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = $RequestModel
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
$env:SEE2THINK_OUTPUT_BASE = $OutputRoot
$env:SEE2THINK_LOG_DIR = "$Root\newlogs\final600_${SafeModel}_vaot_wrong_render_floor_${StartPos}_${EndPos}"

New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

Write-Host "============================================================"
Write-Host "START wrong_render model=$Model request=$RequestModel range=$StartPos..$EndPos workers=$Workers"
Write-Host "tasks=$Tasks"
Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
Write-Host "logs=$env:SEE2THINK_LOG_DIR"
Write-Host "============================================================"

python -u solve/run_tasks.py `
  --tasks $Tasks `
  --mode banana `
  --model $Model `
  --workers $Workers `
  --start $StartPos `
  --end $EndPos `
  --setting vaot_wrong_render `
  --prompt_dir newprompt
