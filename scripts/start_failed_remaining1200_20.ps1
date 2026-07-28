Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

python scripts/build_failed_remaining1200_tasks.py
if ($LASTEXITCODE -ne 0) { throw "Failed to build the failed-task lists." }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\rerun_failed_remaining1200_20_$ts"
New-Item -ItemType Directory -Force $RunDir | Out-Null

# Total worker count is exactly 20 across all nine independent runners.
$jobs = @(
  @{ Name="gpt55_text"; Model="gpt-5.5"; Request="gpt-5.5:floor"; Setting="text_cot"; Workers=2 },
  @{ Name="gpt55_no_render"; Model="gpt-5.5"; Request="gpt-5.5:floor"; Setting="vaot_no_render"; Workers=2 },
  @{ Name="gpt55_wrong_render"; Model="gpt-5.5"; Request="gpt-5.5:floor"; Setting="vaot_wrong_render"; Workers=3 },
  @{ Name="o3_text"; Model="o3"; Request="o3:floor"; Setting="text_cot"; Workers=2 },
  @{ Name="o3_no_render"; Model="o3"; Request="o3:floor"; Setting="vaot_no_render"; Workers=3 },
  @{ Name="o3_wrong_render"; Model="o3"; Request="o3:floor"; Setting="vaot_wrong_render"; Workers=3 },
  @{ Name="gemini_text"; Model="gemini-3.5-flash"; Request="gemini-3.5-flash:floor"; Setting="text_cot"; Workers=1 },
  @{ Name="gemini_no_render"; Model="gemini-3.5-flash"; Request="gemini-3.5-flash:floor"; Setting="vaot_no_render"; Workers=1 },
  @{ Name="gemini_wrong_render"; Model="gemini-3.5-flash"; Request="gemini-3.5-flash:floor"; Setting="vaot_wrong_render"; Workers=3 }
)

$totalWorkers = ($jobs | ForEach-Object { [int]$_.Workers } | Measure-Object -Sum).Sum
if ($totalWorkers -ne 20) {
  throw "Worker allocation must total 20."
}

$records = @()
foreach ($job in $jobs) {
  $tasks = "json/rerun_failed_remaining_600/$($job.Model)__$($job.Setting)__failed.json"
  $count = (Get-Content -LiteralPath $tasks -Raw | ConvertFrom-Json).Count
  if ($count -eq 0) {
    Write-Host "SKIPPED $($job.Name): no failed tasks"
    continue
  }

  $out = "$RunDir\$($job.Name).out"
  $err = "$RunDir\$($job.Name).err"
  # Explicit 0..count avoids find_next_start re-running successful items in the original list.
  $cmd = "& '$Root\scripts\run_remaining1200_one.ps1' -Model '$($job.Model)' -RequestModel '$($job.Request)' -Setting '$($job.Setting)' -Tasks '$tasks' -Workers $($job.Workers) -StartPos 0 -EndPos $count"
  $p = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
  ) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $records += [pscustomobject]@{
    name = $job.Name; model = $job.Model; request_model = $job.Request; setting = $job.Setting
    workers = $job.Workers; task_count = $count; tasks = $tasks; pid = $p.Id; stdout = $out; stderr = $err
  }
  Write-Host "STARTED $($job.Name): pid=$($p.Id), tasks=$count, workers=$($job.Workers)"
}

[pscustomobject]@{
  run_id = $ts; start_time = (Get-Date).ToString("o"); total_workers = 20; run_dir = $RunDir; jobs = $records
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "MANIFEST $RunDir\manifest.json"
