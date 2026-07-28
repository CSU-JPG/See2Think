$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$jobs = @(
  @{
    Name = "gpt55_no_render"
    Model = "gpt-5.5"
    Request = "gpt-5.5:floor"
    Tasks = "json/run_tasks_need_600/gpt-5.5__vaot_no_render__need_600.json"
    Workers = 2
  },
  @{
    Name = "o3_no_render"
    Model = "o3"
    Request = "o3:floor"
    Tasks = "json/run_tasks_need_600/o3__vaot_no_render__need_600.json"
    Workers = 3
  },
  @{
    Name = "gemini_no_render"
    Model = "gemini-3.5-flash"
    Request = "gemini-3.5-flash:floor"
    Tasks = "json/run_tasks_need_600/gemini-3.5-flash__vaot_no_render__need_600.json"
    Workers = 2
  }
)

foreach ($job in $jobs) {
  $env:NR_MODEL = $job.Model
  $env:NR_REQUEST_MODEL = $job.Request
  $env:NR_TASKS = $job.Tasks
  $env:WORKERS = [string]$job.Workers
  $logDir = Join-Path $Root "newlogs\pipeline_launch"
  New-Item -ItemType Directory -Force $logDir | Out-Null
  $out = Join-Path $logDir "$($job.Name).out"
  $err = Join-Path $logDir "$($job.Name).err"
  Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "`$env:NR_MODEL='$($job.Model)'; `$env:NR_REQUEST_MODEL='$($job.Request)'; `$env:NR_TASKS='$($job.Tasks)'; & '$Root\scripts\run_final600_no_render_one.ps1' -Workers $($job.Workers)"
  ) -RedirectStandardOutput $out -RedirectStandardError $err
  Write-Host "STARTED $($job.Name) workers=$($job.Workers)"
  Write-Host "  out=$out"
  Write-Host "  err=$err"
}

