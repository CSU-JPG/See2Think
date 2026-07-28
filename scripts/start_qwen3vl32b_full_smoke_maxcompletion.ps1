param(
  [string]$Tasks = "",
  [int]$StartPos = 0,
  [int]$EndPos = 1,
  [int]$MaxCompletionTokens = 2048,
  [int]$ThinkingBudget = 512,
  [int]$MaxSteps = 10,
  [int]$RequestTimeoutSeconds = 900,
  [int]$TaskTimeoutSeconds = 1800
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
if (-not $env:OPENAI_API_KEY) { throw "OPENAI_API_KEY is missing after importing config.sh" }
if (-not $env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL = "https://yunwu.ai/v1" }

if (-not $Tasks) {
  $latest = Get-ChildItem "$Root\newlogs" -Directory -Filter "qwen3vl32b_status_*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($latest -and (Test-Path (Join-Path $latest.FullName "failed_vaot_full.json"))) {
    $Tasks = Join-Path $latest.FullName "failed_vaot_full.json"
  } else {
    $Tasks = "$Root\json\tasks_see2thinkbench_1200task_available.json"
  }
}

$TasksFull = (Resolve-Path -LiteralPath $Tasks).Path
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\smoke_qwen3vl32b_full_maxcompletion_$ts"
$LogDir = "$Root\newlogs\smoke_qwen3vl32b_full_maxcompletion_logs_$ts"
$OutputBase = "$Root\newtasks\smoke_qwen3vl32b_full_maxcompletion_$ts"
New-Item -ItemType Directory -Force $RunDir, $LogDir, $OutputBase | Out-Null

$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = "qwen3-vl-32b-thinking"
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "$TaskTimeoutSeconds"
$env:SEE2THINK_OPENAI_TIMEOUT_SECONDS = "$RequestTimeoutSeconds"
$env:SEE2THINK_MAX_TOKENS = "0"
$env:SEE2THINK_MAX_COMPLETION_TOKENS = "$MaxCompletionTokens"
$env:SEE2THINK_MAX_STEPS = "$MaxSteps"
$env:SEE2THINK_TOTAL_TOKEN_BUDGET = "8192"
$env:SEE2THINK_EXTRA_BODY_JSON = "{`"thinking_budget`":$ThinkingBudget}"
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
  "--prompt_dir", "prompt"
) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru

[pscustomobject]@{
  start_time = (Get-Date).ToString("o")
  pid = $p.Id
  tasks = $TasksFull
  setting = "vaot_full"
  max_completion_tokens = $MaxCompletionTokens
  max_tokens = 0
  thinking_budget = $ThinkingBudget
  max_steps = $MaxSteps
  request_timeout_seconds = $RequestTimeoutSeconds
  task_timeout_seconds = $TaskTimeoutSeconds
  run_dir = $RunDir
  log_dir = $LogDir
  output_base = $OutputBase
  stdout = $out
  stderr = $err
} | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "STARTED smoke full max_completion: pid=$($p.Id)"
Write-Host "MANIFEST $RunDir\manifest.json"
