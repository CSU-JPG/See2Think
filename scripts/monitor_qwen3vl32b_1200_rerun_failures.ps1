param(
  [string]$Model = "qwen3-vl-32b-thinking",
  [string]$RequestModel = "qwen3-vl-32b-thinking",
  [string]$Tasks = "json/tasks_see2thinkbench_1200task_available.json",
  [double]$WaitHours = 6,
  [int]$PollMinutes = 30,
  [int]$WorkersText = 6,
  [int]$WorkersNoRender = 8,
  [int]$WorkersFull = 8,
  [int]$WorkersWrongRender = 8,
  [int]$MaxTokens = 16384,
  [int]$MaxSteps = 10,
  [int]$TotalTokenBudget = 16384,
  [int]$RequestTimeoutSeconds = 3600,
  [int]$TaskTimeoutSeconds = 14400,
  [switch]$ArchiveFailedDirs
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

function Active-QwenProcesses {
  $safe = Safe-Name $Model
  Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq "python.exe") -and
    ($_.CommandLine -match [regex]::Escape($Model)) -and
    (
      $_.CommandLine -match "solve/run_tasks.py" -or
      $_.CommandLine -match "solve\\run_tasks.py" -or
      $_.CommandLine -match "solve/auto_solve.py" -or
      $_.CommandLine -match "solve\\auto_solve.py" -or
      $_.CommandLine -match "final1200_$safe"
    )
  }
}

function Start-RerunJob {
  param(
    [string]$Name,
    [string]$Setting,
    [string]$Suffix,
    [int]$Workers,
    [string]$TaskFile,
    [string]$RunDir,
    [string]$Timestamp
  )
  $outputBase = "$Root\newtasks\final1200_$(Safe-Name $Model)_$Suffix"
  $logDir = "$Root\newlogs\final1200_$(Safe-Name $Model)_${Setting}_rerun_$Timestamp"
  New-Item -ItemType Directory -Force $outputBase, $logDir | Out-Null
  $out = "$RunDir\$Name.rerun.out"
  $err = "$RunDir\$Name.rerun.err"
  $n = [int](python -c "import json; print(len(json.load(open(r'$TaskFile', encoding='utf-8'))))")
  if ($n -le 0) {
    "[$(Get-Date -Format o)] SKIP $Setting no failed tasks" | Add-Content "$RunDir\monitor.log"
    return $null
  }

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
`$env:SEE2THINK_OUTPUT_BASE='$outputBase'
`$env:SEE2THINK_LOG_DIR='$logDir'
python -u solve/run_tasks.py --tasks '$TaskFile' --mode banana --model '$Model' --workers $Workers --start 0 --end $n --setting '$Setting' --prompt_dir prompt
"@
  $p = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
  ) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  "[$(Get-Date -Format o)] START_RERUN $Setting pid=$($p.Id) tasks=$n workers=$Workers output=$outputBase" | Add-Content "$RunDir\monitor.log"
  return [pscustomobject]@{ name=$Name; setting=$Setting; tasks=$n; workers=$Workers; pid=$p.Id; stdout=$out; stderr=$err; log_dir=$logDir; output_base=$outputBase }
}

Import-ConfigSh "$Root\config.sh"
if (-not $env:OPENAI_API_KEY) {
  throw "OPENAI_API_KEY is missing. Put it in config.sh or set it before running this script."
}
if (-not $env:OPENAI_BASE_URL) {
  $env:OPENAI_BASE_URL = "https://yunwu.ai/v1"
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\qwen3vl32b_api_1200_monitor_rerun_$ts"
New-Item -ItemType Directory -Force $RunDir | Out-Null
"[$(Get-Date -Format o)] MONITOR_START wait_hours=$WaitHours poll_minutes=$PollMinutes" | Set-Content -Encoding UTF8 "$RunDir\monitor.log"

Start-Sleep -Seconds ([int]($WaitHours * 3600))

while ($true) {
  $active = @(Active-QwenProcesses)
  if ($active.Count -eq 0) { break }
  "[$(Get-Date -Format o)] STILL_RUNNING active_python=$($active.Count); next_check_minutes=$PollMinutes" | Add-Content "$RunDir\monitor.log"
  Start-Sleep -Seconds ([int]($PollMinutes * 60))
}

"[$(Get-Date -Format o)] ORIGINAL_RUN_FINISHED scanning failed/incomplete cases" | Add-Content "$RunDir\monitor.log"
$ScanDir = "$RunDir\failed_scan"
python scripts/build_qwen_failed_task_lists.py --tasks $Tasks --model $Model --newtasks-root newtasks --out-dir $ScanDir *> "$RunDir\scan.out"

if ($ArchiveFailedDirs) {
  $archive = "$Root\newtasks\qwen3vl32b_failed_before_rerun_$ts"
  New-Item -ItemType Directory -Force $archive | Out-Null
  Import-Csv "$ScanDir\failed_cases.csv" | ForEach-Object {
    $src = $_.output_dir
    if (Test-Path $src) {
      $rel = Resolve-Path -LiteralPath $src -Relative
      $safeRel = ($rel -replace "^\.[\\/]", "" -replace ":", "" -replace "[\\/]", "__")
      Move-Item -LiteralPath $src -Destination (Join-Path $archive $safeRel) -Force
    }
  }
  "[$(Get-Date -Format o)] ARCHIVED_FAILED_DIRS archive=$archive" | Add-Content "$RunDir\monitor.log"
}

$jobs = @(
  @{ Name="text"; Setting="text_cot"; Suffix="text_cot"; Workers=$WorkersText; TaskFile="$ScanDir\failed_text_cot.json" },
  @{ Name="no_render"; Setting="vaot_no_render"; Suffix="vaot_no_render"; Workers=$WorkersNoRender; TaskFile="$ScanDir\failed_vaot_no_render.json" },
  @{ Name="full"; Setting="vaot_full"; Suffix="vaot_full_floor"; Workers=$WorkersFull; TaskFile="$ScanDir\failed_vaot_full.json" },
  @{ Name="wrong_render"; Setting="vaot_wrong_render"; Suffix="vaot_wrong_render_floor"; Workers=$WorkersWrongRender; TaskFile="$ScanDir\failed_vaot_wrong_render.json" }
)

$started = @()
foreach ($job in $jobs) {
  $r = Start-RerunJob -Name $job.Name -Setting $job.Setting -Suffix $job.Suffix -Workers $job.Workers -TaskFile $job.TaskFile -RunDir $RunDir -Timestamp $ts
  if ($null -ne $r) { $started += $r }
}

[pscustomobject]@{
  start_time = (Get-Date).ToString("o")
  model = $Model
  request_model = $RequestModel
  tasks = $Tasks
  max_tokens = $MaxTokens
  max_steps = $MaxSteps
  total_token_budget = $TotalTokenBudget
  request_timeout_seconds = $RequestTimeoutSeconds
  task_timeout_seconds = $TaskTimeoutSeconds
  scan_dir = $ScanDir
  rerun_jobs = $started
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

"[$(Get-Date -Format o)] MONITOR_DONE rerun_jobs=$($started.Count)" | Add-Content "$RunDir\monitor.log"
Write-Host "MONITOR_DIR $RunDir"

