param(
  [string]$Model = "qwen3-vl-32b-thinking",
  [string]$RequestModel = "qwen3-vl-32b-thinking",
  [string]$Tasks = "json/tasks_see2thinkbench_1200task_available.json",
  [int]$WorkersText = 6,
  [int]$WorkersNoRender = 8,
  [int]$WorkersFull = 8,
  [int]$WorkersWrongRender = 8,
  [int]$MaxTokens = 2048,
  [int]$MaxSteps = 10,
  [int]$TotalTokenBudget = 16384,
  [int]$RequestTimeoutSeconds = 600,
  [int]$TaskTimeoutSeconds = 7200,
  [string]$ExtraBodyJson = "",
  [int]$StartPos = 0,
  [int]$EndPos = -1
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

function Count-Tasks {
  param([string]$Path)
  return [int](python -c "import json; print(len(json.load(open(r'$Path', encoding='utf-8'))))")
}

Import-ConfigSh "$Root\config.sh"
if (-not $env:OPENAI_API_KEY) {
  throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
  $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

if ($EndPos -lt 0) {
  $EndPos = Count-Tasks $Tasks
}

$SafeModel = Safe-Name $Model
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\qwen3vl32b_api_1200_$ts"
New-Item -ItemType Directory -Force $RunDir | Out-Null

$jobs = @(
  @{ Name="text"; Setting="text_cot"; Suffix="text_cot"; Workers=$WorkersText },
  @{ Name="no_render"; Setting="vaot_no_render"; Suffix="vaot_no_render"; Workers=$WorkersNoRender },
  @{ Name="full"; Setting="vaot_full"; Suffix="vaot_full_floor"; Workers=$WorkersFull },
  @{ Name="wrong_render"; Setting="vaot_wrong_render"; Suffix="vaot_wrong_render_floor"; Workers=$WorkersWrongRender }
)

$totalWorkers = ($jobs | ForEach-Object { [int]$_.Workers } | Measure-Object -Sum).Sum
$records = @()

foreach ($job in $jobs) {
  $outputBase = "$Root\newtasks\final1200_${SafeModel}_$($job.Suffix)"
  $logDir = "$Root\newlogs\final1200_${SafeModel}_$($job.Setting)_${StartPos}_${EndPos}_$ts"
  New-Item -ItemType Directory -Force $outputBase, $logDir | Out-Null

  $out = "$RunDir\$($job.Name).out"
  $err = "$RunDir\$($job.Name).err"
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
`$env:SEE2THINK_EXTRA_BODY_JSON='$ExtraBodyJson'
`$env:SEE2THINK_OUTPUT_BASE='$outputBase'
`$env:SEE2THINK_LOG_DIR='$logDir'
python -u solve/run_tasks.py --tasks '$Tasks' --mode banana --model '$Model' --workers $($job.Workers) --start $StartPos --end $EndPos --setting '$($job.Setting)' --prompt_dir newprompt
"@
  $p = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
  ) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru

  $records += [pscustomobject]@{
    name = $job.Name
    model = $Model
    request_model = $RequestModel
    setting = $job.Setting
    workers = $job.Workers
    start = $StartPos
    end = $EndPos
    output_base = $outputBase
    log_dir = $logDir
    pid = $p.Id
    stdout = $out
    stderr = $err
  }
  Write-Host "STARTED $($job.Name): pid=$($p.Id), workers=$($job.Workers), output=$outputBase"
}

[pscustomobject]@{
  run_id = $ts
  start_time = (Get-Date).ToString("o")
  model = $Model
  request_model = $RequestModel
  tasks = $Tasks
  start = $StartPos
  end = $EndPos
  total_workers = $totalWorkers
  max_tokens = $MaxTokens
  max_steps = $MaxSteps
  total_token_budget = $TotalTokenBudget
  request_timeout_seconds = $RequestTimeoutSeconds
  task_timeout_seconds = $TaskTimeoutSeconds
  extra_body_json = $ExtraBodyJson
  run_dir = $RunDir
  jobs = $records
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "TOTAL_WORKERS $totalWorkers"
Write-Host "MANIFEST $RunDir\manifest.json"
