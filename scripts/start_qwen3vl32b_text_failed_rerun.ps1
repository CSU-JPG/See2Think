param(
  [string]$Model = "qwen3-vl-32b-thinking",
  [string]$RequestModel = "qwen3-vl-32b-thinking",
  [string]$TaskFile,
  [int]$Workers = 6,
  [int]$MaxTokens = 16384,
  [int]$MaxSteps = 10,
  [int]$TotalTokenBudget = 16384,
  [int]$RequestTimeoutSeconds = 3600,
  [int]$TaskTimeoutSeconds = 14400
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

if (-not $TaskFile) {
  throw "TaskFile is required."
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
$RunDir = "$Root\newlogs\qwen3vl32b_text_failed_rerun_$ts"
$LogDir = "$Root\newlogs\final1200_${SafeModel}_text_cot_failed_rerun_$ts"
$OutputBase = "$Root\newtasks\final1200_${SafeModel}_text_cot"
New-Item -ItemType Directory -Force $RunDir, $LogDir, $OutputBase | Out-Null

$TaskFileFull = (Resolve-Path -LiteralPath $TaskFile).Path
$n = [int](python -c "import json; print(len(json.load(open(r'$TaskFileFull', encoding='utf-8'))))")

$out = "$RunDir\text_failed_rerun.out"
$err = "$RunDir\text_failed_rerun.err"
$cmd = @"
Set-Location '$Root'
`$env:PYTHONIOENCODING='utf-8'
`$env:SKIP_CONFIRM='1'
`$env:SEE2THINK_DATA_BASE='$Root'
`$env:SEE2THINK_LLM_BACKEND='openai'
`$env:SEE2THINK_REQUEST_MODEL='$RequestModel'
`$env:SEE2THINK_TASK_TIMEOUT_SECONDS='$TaskTimeoutSeconds'
`$env:SEE2THINK_OPENAI_TIMEOUT_SECONDS='$RequestTimeoutSeconds'
`$env:SEE2THINK_MAX_TOKENS='$MaxTokens'
`$env:SEE2THINK_MAX_STEPS='$MaxSteps'
`$env:SEE2THINK_TOTAL_TOKEN_BUDGET='$TotalTokenBudget'
`$env:SEE2THINK_EXTRA_BODY_JSON=''
`$env:SEE2THINK_OUTPUT_BASE='$OutputBase'
`$env:SEE2THINK_LOG_DIR='$LogDir'
python -u solve/run_tasks.py --tasks '$TaskFileFull' --mode banana --model '$Model' --workers $Workers --start 0 --end $n --setting 'text_cot' --prompt_dir newprompt
"@

$p = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru

[pscustomobject]@{
  start_time = (Get-Date).ToString("o")
  model = $Model
  request_model = $RequestModel
  task_file = $TaskFileFull
  tasks = $n
  workers = $Workers
  max_tokens = $MaxTokens
  max_steps = $MaxSteps
  total_token_budget = $TotalTokenBudget
  request_timeout_seconds = $RequestTimeoutSeconds
  task_timeout_seconds = $TaskTimeoutSeconds
  pid = $p.Id
  run_dir = $RunDir
  log_dir = $LogDir
  stdout = $out
  stderr = $err
  output_base = $OutputBase
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "STARTED text failed rerun: pid=$($p.Id), tasks=$n"
Write-Host "MANIFEST $RunDir\manifest.json"

