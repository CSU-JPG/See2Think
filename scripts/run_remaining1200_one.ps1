param(
  [Parameter(Mandatory=$true)][string]$Model,
  [Parameter(Mandatory=$true)][string]$RequestModel,
  [Parameter(Mandatory=$true)][string]$Setting,
  [Parameter(Mandatory=$true)][string]$Tasks,
  [int]$Workers = 4,
  [int]$StartPos = -1,
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

Import-ConfigSh "$Root\config.sh"

$SafeModel = Safe-Name $Model
$OutputSuffix = switch ($Setting) {
  "text_cot" { "text_cot" }
  "vaot_no_render" { "vaot_no_render" }
  "vaot_wrong_render" { "vaot_wrong_render_floor" }
  default { throw "Unsupported setting: $Setting" }
}
$RequireRender = $Setting -eq "vaot_wrong_render"
$OutputRoot = "$Root\newtasks\final1200_${SafeModel}_${OutputSuffix}"
$Subdir = "banana_${Model}_${Setting}"

$findArgs = @(
  "scripts/find_next_start.py",
  "--tasks", $Tasks,
  "--output-root", $OutputRoot,
  "--subdir", $Subdir
)
if ($RequireRender) { $findArgs += "--require-render" }
$DefaultStart = python @findArgs

if ($StartPos -lt 0) { $StartPos = [int]$DefaultStart }
if ($EndPos -lt 0) {
  $EndPos = [int](python -c "import json; print(len(json.load(open(r'$Tasks', encoding='utf-8'))))")
}

$env:OPENAI_BASE_URL = if ($env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL } else { "https://yunwu.ai/v1" }
$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = $RequestModel
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
$env:SEE2THINK_OUTPUT_BASE = $OutputRoot
$env:SEE2THINK_LOG_DIR = "$Root\newlogs\final1200_remaining_${SafeModel}_${Setting}_${StartPos}_${EndPos}"

New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE, $env:SEE2THINK_LOG_DIR | Out-Null

Write-Host "============================================================"
Write-Host "START remaining1200 model=$Model request=$RequestModel setting=$Setting range=$StartPos..$EndPos workers=$Workers"
Write-Host "tasks=$Tasks"
Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
Write-Host "logs=$env:SEE2THINK_LOG_DIR"
Write-Host "============================================================"

python -u solve/run_tasks.py `
  --tasks $Tasks `
  --mode banana `
  --model $Model `
  --workers $Workers `
  --start $StartPos `
  --end $EndPos `
  --setting $Setting `
  --prompt_dir prompt
