param(
  [Parameter(Mandatory=$true)][string]$Setting,
  [string]$Model = "qwen3-vl-32b-thinking",
  [string]$RequestModel = "qwen3-vl-32b-thinking",
  [string]$Tasks = "json/tasks_see2thinkbench_1200task_available.json",
  [int]$Workers = 4,
  [int]$StartPos = 0,
  [int]$EndPos = -1,
  [int]$MaxTokens = 16384,
  [int]$MaxCompletionTokens = 0,
  [int]$MaxSteps = 10,
  [int]$TotalTokenBudget = 16384,
  [int]$RequestTimeoutSeconds = 3600,
  [int]$TaskTimeoutSeconds = 14400,
  [string]$ExtraBodyJson = "",
  [string]$OpenAIBaseUrl = "",
  [string]$OpenAIApiKey = "",
  [string]$GeminiBaseUrl = "",
  [string]$GeminiApiKey = ""
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

function Normalize-ProcessPathEnv {
  $pathValue = [Environment]::GetEnvironmentVariable("Path", "Process")
  $PATHValue = [Environment]::GetEnvironmentVariable("PATH", "Process")
  if ($pathValue -and $PATHValue) {
    [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
  }
}

function Count-Tasks {
  param([string]$Path)
  $full = (Resolve-Path -LiteralPath $Path).Path
  return [int](python -c "import json; print(len(json.load(open(r'$full', encoding='utf-8'))))")
}

switch ($Setting) {
  "text_cot" { $Suffix = "text_cot"; $Name = "text" }
  "vaot_no_render" { $Suffix = "vaot_no_render"; $Name = "no_render" }
  "vaot_full" { $Suffix = "vaot_full_floor"; $Name = "full" }
  "vaot_wrong_render" { $Suffix = "vaot_wrong_render_floor"; $Name = "wrong_render" }
  default { throw "Unsupported setting: $Setting" }
}

Import-ConfigSh "$Root\config.sh"
if ($OpenAIBaseUrl) {
  $env:OPENAI_BASE_URL = $OpenAIBaseUrl
}
if ($OpenAIApiKey) {
  $env:OPENAI_API_KEY = $OpenAIApiKey
}
if ($GeminiBaseUrl) {
  $env:GEMINI_BASE_URL = $GeminiBaseUrl
}
if ($GeminiApiKey) {
  $env:GEMINI_API_KEY = $GeminiApiKey
}
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
$PythonExe = (Get-Command python -ErrorAction Stop).Source
$PowerShellExe = Join-Path $PSHOME "powershell.exe"
$PythonExeForCmd = $PythonExe.Replace("'", "''")
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = "$Root\newlogs\qwen3vl32b_api_${Name}_resume_$ts"
$OutputBase = "$Root\newtasks\final1200_${SafeModel}_$Suffix"
$LogDir = "$Root\newlogs\final1200_${SafeModel}_${Setting}_resume_$ts"
New-Item -ItemType Directory -Force $RunDir, $OutputBase, $LogDir | Out-Null

$TasksFull = (Resolve-Path -LiteralPath $Tasks).Path
$out = "$RunDir\$Name.out"
$err = "$RunDir\$Name.err"
Normalize-ProcessPathEnv
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
`$env:SEE2THINK_MAX_COMPLETION_TOKENS='$MaxCompletionTokens'
`$env:SEE2THINK_MAX_STEPS='$MaxSteps'
`$env:SEE2THINK_TOTAL_TOKEN_BUDGET='$TotalTokenBudget'
`$env:SEE2THINK_EXTRA_BODY_JSON='$ExtraBodyJson'
`$env:SEE2THINK_OUTPUT_BASE='$OutputBase'
`$env:SEE2THINK_LOG_DIR='$LogDir'
& '$PythonExeForCmd' -u solve/run_tasks.py --tasks '$TasksFull' --mode banana --model '$Model' --workers $Workers --start $StartPos --end $EndPos --setting '$Setting' --prompt_dir newprompt
"@
$p = Start-Process -FilePath $PowerShellExe -WindowStyle Hidden -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru

[pscustomobject]@{
  start_time = (Get-Date).ToString("o")
  setting = $Setting
  model = $Model
  request_model = $RequestModel
  tasks = $TasksFull
  start = $StartPos
  end = $EndPos
  workers = $Workers
  process_id = $p.Id
  run_dir = $RunDir
  log_dir = $LogDir
  stdout = $out
  stderr = $err
  output_base = $OutputBase
  openai_base_url = $env:OPENAI_BASE_URL
  openai_api_key = if ($OpenAIApiKey) { "provided_parameter_redacted" } else { "config_or_environment_redacted" }
  gemini_base_url = $env:GEMINI_BASE_URL
  gemini_api_key = if ($GeminiApiKey) { "provided_parameter_redacted" } else { "config_or_environment_redacted" }
  max_tokens = $MaxTokens
  max_completion_tokens = $MaxCompletionTokens
  max_steps = $MaxSteps
  total_token_budget = $TotalTokenBudget
  extra_body_json = $ExtraBodyJson
  request_timeout_seconds = $RequestTimeoutSeconds
  task_timeout_seconds = $TaskTimeoutSeconds
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "STARTED $Setting resume: pid=$($p.Id), range=$StartPos..$EndPos, workers=$Workers"
Write-Host "MANIFEST $RunDir\manifest.json"

