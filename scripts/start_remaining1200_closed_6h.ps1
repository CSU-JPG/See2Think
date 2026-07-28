param(
  [int]$WorkersText = 4,
  [int]$WorkersNoRender = 4,
  [int]$WorkersWrongRender = 3,
  [int]$StopAfterSeconds = 21600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

python scripts/build_remaining_600_tasks.py

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\remaining1200_closed_6h_$ts"
New-Item -ItemType Directory -Force $RunDir | Out-Null

$jobs = @(
  @{ Name="gpt55_text"; Model="gpt-5.5"; Request="gpt-5.5:floor"; Setting="text_cot"; Workers=$WorkersText },
  @{ Name="gpt55_no_render"; Model="gpt-5.5"; Request="gpt-5.5:floor"; Setting="vaot_no_render"; Workers=$WorkersNoRender },
  @{ Name="gpt55_wrong_render"; Model="gpt-5.5"; Request="gpt-5.5:floor"; Setting="vaot_wrong_render"; Workers=$WorkersWrongRender },
  @{ Name="o3_text"; Model="o3"; Request="o3:floor"; Setting="text_cot"; Workers=$WorkersText },
  @{ Name="o3_no_render"; Model="o3"; Request="o3:floor"; Setting="vaot_no_render"; Workers=$WorkersNoRender },
  @{ Name="o3_wrong_render"; Model="o3"; Request="o3:floor"; Setting="vaot_wrong_render"; Workers=$WorkersWrongRender },
  @{ Name="gemini_text"; Model="gemini-3.5-flash"; Request="gemini-3.5-flash:floor"; Setting="text_cot"; Workers=$WorkersText },
  @{ Name="gemini_no_render"; Model="gemini-3.5-flash"; Request="gemini-3.5-flash:floor"; Setting="vaot_no_render"; Workers=$WorkersNoRender },
  @{ Name="gemini_wrong_render"; Model="gemini-3.5-flash"; Request="gemini-3.5-flash:floor"; Setting="vaot_wrong_render"; Workers=$WorkersWrongRender }
)

$records = @()
foreach ($job in $jobs) {
  $tasks = "json/run_tasks_remaining_600/$($job.Model)__$($job.Setting)__remaining_600.json"
  $out = "$RunDir\$($job.Name).out"
  $err = "$RunDir\$($job.Name).err"
  $cmd = "& '$Root\scripts\run_remaining1200_one.ps1' -Model '$($job.Model)' -RequestModel '$($job.Request)' -Setting '$($job.Setting)' -Tasks '$tasks' -Workers $($job.Workers)"
  $p = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $cmd
  ) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $records += [pscustomobject]@{
    name = $job.Name
    model = $job.Model
    request_model = $job.Request
    setting = $job.Setting
    workers = $job.Workers
    tasks = $tasks
    pid = $p.Id
    stdout = $out
    stderr = $err
  }
  Write-Host "STARTED $($job.Name) pid=$($p.Id) workers=$($job.Workers)"
}

$manifest = [pscustomobject]@{
  run_id = $ts
  start_time = (Get-Date).ToString("o")
  stop_after_seconds = $StopAfterSeconds
  run_dir = $RunDir
  jobs = $records
}
$manifestPath = "$RunDir\manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $manifestPath

$pidList = ($records | ForEach-Object { $_.pid }) -join ","
$watchOut = "$RunDir\watchdog.out"
$watchErr = "$RunDir\watchdog.err"
$watchCmd = @"
Start-Sleep -Seconds $StopAfterSeconds
`$pids = @($pidList)
function Stop-Tree([int]`$PidValue) {
  `$children = Get-CimInstance Win32_Process | Where-Object { `$_.ParentProcessId -eq `$PidValue }
  foreach (`$child in `$children) { Stop-Tree ([int]`$child.ProcessId) }
  Stop-Process -Id `$PidValue -Force -ErrorAction SilentlyContinue
}
foreach (`$pid in `$pids) { Stop-Tree ([int]`$pid) }
"STOPPED at $((Get-Date).ToString('o')) after $StopAfterSeconds seconds pids=$pidList" | Set-Content -Encoding UTF8 "$RunDir\STOPPED_BY_WATCHDOG.txt"
"@
$watch = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-Command", $watchCmd
) -RedirectStandardOutput $watchOut -RedirectStandardError $watchErr -PassThru

Write-Host "WATCHDOG pid=$($watch.Id) stop_after_seconds=$StopAfterSeconds"
Write-Host "MANIFEST $manifestPath"
