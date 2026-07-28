Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Import-ConfigSh {
    param([string]$Path)
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

if (-not $env:MASK_MODEL) { throw "MASK_MODEL is required" }
if (-not $env:MASK_REQUEST_MODEL) { throw "MASK_REQUEST_MODEL is required" }
if (-not $env:MASK_TASKS) { throw "MASK_TASKS is required" }
if (-not $env:MASK_SETTING) { throw "MASK_SETTING is required: vaot_full or vaot_wrong_render" }

$Model = $env:MASK_MODEL
$RequestModel = $env:MASK_REQUEST_MODEL
$Tasks = $env:MASK_TASKS
$Setting = $env:MASK_SETTING
$Workers = if ($env:WORKERS) { [int]$env:WORKERS } else { 1 }
$SafeModel = Safe-Name $Model

if ($Setting -eq "vaot_full") {
    $OutputRoot = "$Root\newtasks\masked_action_audit120_${SafeModel}_vaot_full_floor"
    $LogName = "masked_action_audit120_${SafeModel}_vaot_full"
} elseif ($Setting -eq "vaot_wrong_render") {
    $OutputRoot = "$Root\newtasks\masked_action_audit120_${SafeModel}_vaot_wrong_render_floor"
    $LogName = "masked_action_audit120_${SafeModel}_vaot_wrong_render"
} else {
    throw "Unsupported MASK_SETTING=$Setting"
}

$env:SKIP_CONFIRM = "1"
$env:SEE2THINK_DATA_BASE = $Root
$env:SEE2THINK_LLM_BACKEND = "openai"
$env:SEE2THINK_REQUEST_MODEL = $RequestModel
$env:SEE2THINK_TASK_TIMEOUT_SECONDS = "1200"
$env:SEE2THINK_OUTPUT_BASE = $OutputRoot
$env:SEE2THINK_LOG_DIR = "$Root\newlogs\$LogName"
$env:SEE2THINK_MASK_ACTION = "1"

New-Item -ItemType Directory -Force $env:SEE2THINK_OUTPUT_BASE | Out-Null
New-Item -ItemType Directory -Force $env:SEE2THINK_LOG_DIR | Out-Null

Write-Host "============================================================"
Write-Host "START masked-action audit model=$Model request=$RequestModel setting=$Setting workers=$Workers"
Write-Host "tasks=$Tasks"
Write-Host "output=$env:SEE2THINK_OUTPUT_BASE"
Write-Host "mask=$env:SEE2THINK_MASK_ACTION"
Write-Host "============================================================"

python -u solve/run_tasks.py `
  --tasks $Tasks `
  --mode banana `
  --model $Model `
  --workers $Workers `
  --start 0 `
  --end 999999 `
  --setting $Setting `
  --prompt_dir newprompt
