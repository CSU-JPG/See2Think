param(
  [string]$Tasks = "",
  [int]$StartPos = 0,
  [int]$EndPos = 1,
  [int]$MaxTokens = 2048,
  [int]$MaxSteps = 10,
  [int]$RequestTimeoutSeconds = 1800,
  [int]$TaskTimeoutSeconds = 3600,
  [string]$ExtraBodyJson = '{"thinking_budget":512}'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Import-ConfigSh {
  param([string]$Path)
  if (!(Test-Path $Path)) { return }
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
  throw "OPENAI_API_KEY is missing after importing config.sh"
}
if (-not $env:OPENAI_BASE_URL) {
  $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

if (-not $Tasks) {
  $latest = Get-ChildItem "$Root\newlogs" -Directory -Filter "qwen3vl32b_status_*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $latest) { throw "No qwen3vl32b_status_* directory found." }
  $Tasks = Join-Path $latest.FullName "failed_vaot_full.json"
}

$TasksFull = (Resolve-Path -LiteralPath $Tasks).Path
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\smoke_qwen3vl32b_full_budget512_$ts"
$LogDir = "$Root\newlogs\smoke_qwen3vl32b_full_budget512_logs_$ts"
$OutputBase = "$Root\newtasks\smoke_qwen3vl32b_full_budget512_$ts"
New-Item -ItemType Directory -Force $RunDir, $LogDir, $OutputBase | Out-Null

$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = "qwen3-vl-32b-thinking"
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "$TaskTimeoutSeconds"
$env:SEE2THINK_OPENAI_TIMEOUT_SECONDS = "$RequestTimeoutSeconds"
$env:SEE2THINK_MAX_TOKENS = "$MaxTokens"
$env:SEE2THINK_MAX_STEPS = "$MaxSteps"
$env:SEE2THINK_TOTAL_TOKEN_BUDGET = "8192"
$env:SEE2THINK_EXTRA_BODY_JSON = $ExtraBodyJson
$env:SEE2THINK_OUTPUT_BASE = $OutputBase
$env:SEE2THINK_LOG_DIR = $LogDir

$out = "$RunDir\out.log"
$err = "$RunDir\err.log"
$p = Start-Process python -WindowStyle Hidden -ArgumentList @(
  "-u", "solve/run_tasks.py",
  "--tasks", $TasksFull,
  "--mode", "banana",
  "--model", "qwen3-vl-32b-thinking",
  "--workers", "1",
  "--start", "$StartPos",
  "--end", "$EndPos",
  "--setting", "vaot_full",
  "--prompt_dir", "newprompt"
) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru

[pscustomobject]@{
  start_time = (Get-Date).ToString("o")
  pid = $p.Id
  setting = "vaot_full"
  tasks = $TasksFull
  start = $StartPos
  end = $EndPos
  max_tokens = $MaxTokens
  max_steps = $MaxSteps
  extra_body_json = $ExtraBodyJson
  run_dir = $RunDir
  log_dir = $LogDir
  output_base = $OutputBase
  stdout = $out
  stderr = $err
} | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "STARTED smoke full: pid=$($p.Id)"
Write-Host "MANIFEST $RunDir\manifest.json"
