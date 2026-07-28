param(
  [string]$Model = $env:NR_MODEL,
  [string]$RequestModel = $env:NR_REQUEST_MODEL,
  [string]$Tasks = $env:NR_TASKS,
  [int]$Workers = 1,
  [int]$StartPos = -1,
  [int]$EndPos = -1
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Import-ConfigSh {
  param([string]$Path)
  if (!(Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    if ($_ -match '^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
      $name = $matches[1]
      $value = $matches[2] -replace '\s+#.*$', ''
      $value = $value.Trim().Trim('"').Trim("'")
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
}

Import-ConfigSh "$Root\config.sh"

if (!$Model -or !$RequestModel -or !$Tasks) {
  throw "Set NR_MODEL, NR_REQUEST_MODEL, and NR_TASKS, or pass -Model/-RequestModel/-Tasks."
}

$env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_REQUEST_MODEL = $RequestModel
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
$env:SKIP_CONFIRM = "1"

$SafeModel = $Model -replace ":", "-"
$env:SEE2THINK_OUTPUT_BASE = Join-Path $Root "newtasks\final600_${SafeModel}_vaot_no_render"
$env:SEE2THINK_LOG_DIR = Join-Path $Root "newlogs\final600_${SafeModel}_vaot_no_render"
New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE, $env:SEE2THINK_LOG_DIR | Out-Null

$taskCount = python -c "import json; print(len(json.load(open(r'$Tasks', encoding='utf-8'))))"
if ($StartPos -lt 0) { $StartPos = 0 }
if ($EndPos -lt 0) { $EndPos = [int]$taskCount }

Write-Host "RUN no_render model=$Model request=$RequestModel start=$StartPos end=$EndPos workers=$Workers"
Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
Write-Host "logs=$env:SEE2THINK_LOG_DIR"

python -u solve/run_tasks.py `
  --tasks $Tasks `
  --mode banana `
  --model $Model `
  --workers $Workers `
  --start $StartPos `
  --end $EndPos `
  --linear `
  --setting vaot_no_render `
  --prompt_dir newprompt

