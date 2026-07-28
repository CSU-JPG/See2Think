Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Import-ConfigSh {
  param([string]$Path)
  foreach ($line in Get-Content -LiteralPath $Path) {
    if ($line -match '^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
      $name = $Matches[1]
      $value = ($Matches[2] -replace '\s+#.*$', '').Trim()
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
      [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
  }
}

Import-ConfigSh "$Root\config.sh"
$PythonExe = (Get-Command python -ErrorAction Stop).Source
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = "$Root\newlogs\acc_eval_rerun_$ts"
$InputDir = "$Root\neweval\results\acc_eval_rerun_$ts\inputs"
New-Item -ItemType Directory -Force $RunDir, $InputDir | Out-Null

$models = @(
  @{ Name='gpt-5.5'; Safe='gpt-5.5'; Tag='gpt55' },
  @{ Name='o3'; Safe='o3'; Tag='o3' },
  @{ Name='gemini-3.5-flash'; Safe='gemini-3.5-flash'; Tag='gemini35flash' }
)
$settings = @('text_only', 'no_render', 'wrong_render')
$records = @()

# Nine answer-judge jobs, each with one worker. Exact matches do not consume a judge-model call.
foreach ($model in $models) {
  foreach ($setting in $settings) {
    $input = "$InputDir\$($model.Tag)_$setting.jsonl"
    $manifest = "$Root\final_results\$setting\$($model.Safe)\_manifest.csv"
    & $PythonExe neweval/build_answer_input.py `
      --tasks json/tasks_see2thinkbench_600_no_gpt5_step1.json `
      --data-base . `
      --manifest $manifest `
      --output-jsonl $input `
      --model $model.Name `
      --setting $setting
    if ($LASTEXITCODE -ne 0) { throw "Failed to build answer input for $($model.Name)/$setting" }

    $runName = "answer_rerun_$ts`_$($model.Tag)_$setting"
    $stdout = "$RunDir\$runName.out"
    $stderr = "$RunDir\$runName.err"
    $args = @('-u', 'neweval/answer_judge.py', '--input-jsonl', $input, '--run-name', $runName, '--judge-model', 'gpt-5.4', '--workers', '1', '--fast-exact')
    $p = Start-Process -FilePath $PythonExe -ArgumentList $args -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $records += [pscustomobject]@{type='accuracy'; model=$model.Name; setting=$setting; workers=1; pid=$p.Id; run_name=$runName; input=$input; stdout=$stdout; stderr=$stderr}
    Write-Host "STARTED accuracy $($model.Name)/$setting pid=$($p.Id)"
  }
}

# Process-level evaluation is defined for VAoT-Full. It is re-run on the aligned 600-sample Full outputs.
foreach ($model in $models) {
  $runName = "key_step_metric_rerun_$ts`_$($model.Tag)_full600"
  $stdout = "$RunDir\$runName.out"
  $stderr = "$RunDir\$runName.err"
  $args = @('-u', 'neweval/key_step_metric_judge.py', '--tasks', 'json/tasks_see2thinkbench_600_no_gpt5_step1.json', '--results-root', 'final_results/full', '--model', $model.Safe, '--run-name', $runName, '--judge-model', 'gpt-5.4', '--workers', '1')
  $p = Start-Process -FilePath $PythonExe -ArgumentList $args -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  $records += [pscustomobject]@{type='process_eval'; model=$model.Name; setting='full'; workers=1; pid=$p.Id; run_name=$runName; input='json/tasks_see2thinkbench_600_no_gpt5_step1.json'; stdout=$stdout; stderr=$stderr}
  Write-Host "STARTED process eval $($model.Name)/full pid=$($p.Id)"
}

[pscustomobject]@{
  run_id = $ts
  start_time = (Get-Date).ToString('o')
  total_workers = 12
  run_dir = $RunDir
  records = $records
} | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "MANIFEST $RunDir\manifest.json"
