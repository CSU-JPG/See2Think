param(
  [string]$Model = "qwen3-vl-32b-thinking",
  [string]$RequestModel = "qwen3-vl-32b-thinking",
  [string]$Tasks = "json/tasks_see2thinkbench_1200task_available.json",
  [int]$Workers = 1,
  [int]$MaxTokens = 2048,
  [int]$MaxSteps = 10,
  [int]$TotalTokenBudget = 16384,
  [int]$RequestTimeoutSeconds = 300,
  [int]$TaskTimeoutSeconds = 900,
  [int]$MaxRetries = 1,
  [string]$ExtraBodyJson = '{"thinking_budget":512}',
  [int]$StartPos = 0,
  [int]$EndPos = 3
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

$SafeModel = Safe-Name $Model
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\qwen3vl32b_api_smoke3_$ts"
$OutputBase = "$Root\newtasks\smoke3_${SafeModel}_vaot_full_floor"
$LogDir = "$Root\newlogs\smoke3_${SafeModel}_vaot_full_${StartPos}_${EndPos}_$ts"
New-Item -ItemType Directory -Force $RunDir, $OutputBase, $LogDir | Out-Null

$out = "$RunDir\full.out"
$err = "$RunDir\full.err"
$cmd = @"
Set-Location '$Root'
`$env:PYTHONIOENCODING='utf-8'
`$env:SKIP_CONFIRM='1'
`$env:SEE2THINK_DATA_BASE='$Root'
`$env:SEE2THINK_LLM_BACKEND='openai'
`$env:SEE2THINK_REQUEST_MODEL='$RequestModel'
`$env:SEE2THINK_TASK_TIMEOUT_SECONDS='$TaskTimeoutSeconds'
`$env:SEE2THINK_OPENAI_TIMEOUT_SECONDS='$RequestTimeoutSeconds'
`$env:SEE2THINK_OPENAI_MAX_RETRIES='$MaxRetries'
`$env:SEE2THINK_MAX_TOKENS='$MaxTokens'
`$env:SEE2THINK_MAX_STEPS='$MaxSteps'
`$env:SEE2THINK_TOTAL_TOKEN_BUDGET='$TotalTokenBudget'
`$env:SEE2THINK_EXTRA_BODY_JSON='$ExtraBodyJson'
`$env:SEE2THINK_OUTPUT_BASE='$OutputBase'
`$env:SEE2THINK_LOG_DIR='$LogDir'
python -u solve/run_tasks.py --tasks '$Tasks' --mode banana --model '$Model' --workers $Workers --start $StartPos --end $EndPos --setting vaot_full --prompt_dir newprompt
"@

$p = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru

[pscustomobject]@{
  run_id = $ts
  start_time = (Get-Date).ToString("o")
  model = $Model
  request_model = $RequestModel
  setting = "vaot_full"
  tasks = $Tasks
  start = $StartPos
  end = $EndPos
  workers = $Workers
  max_tokens = $MaxTokens
  max_steps = $MaxSteps
  total_token_budget = $TotalTokenBudget
  request_timeout_seconds = $RequestTimeoutSeconds
  task_timeout_seconds = $TaskTimeoutSeconds
  max_retries = $MaxRetries
  extra_body_json = $ExtraBodyJson
  output_base = $OutputBase
  log_dir = $LogDir
  pid = $p.Id
  stdout = $out
  stderr = $err
} | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "STARTED qwen smoke3 full: pid=$($p.Id), workers=$Workers"
Write-Host "OUTPUT $OutputBase"
Write-Host "LOGDIR $LogDir"
Write-Host "MANIFEST $RunDir\manifest.json"
