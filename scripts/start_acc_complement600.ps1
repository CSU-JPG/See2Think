Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

foreach ($line in Get-Content -LiteralPath "$Root\config.sh") {
  if ($line -match '^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
    $v = ($Matches[2] -replace '\s+#.*$', '').Trim().Trim('"').Trim("'")
    [Environment]::SetEnvironmentVariable($Matches[1], $v, 'Process')
  }
}

$PythonExe = (Get-Command python -ErrorAction Stop).Source
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = "$Root\newlogs\acc_complement600_$ts"
$InputDir = "$Root\eval\results\acc_complement600_$ts\inputs"
$Tasks = "$Root\json\tasks_see2thinkbench_complement600.json"
New-Item -ItemType Directory -Force $RunDir, $InputDir | Out-Null

$models = @(
  @{ Name='gpt-5.5'; Safe='gpt-5.5'; Tag='gpt55' },
  @{ Name='o3'; Safe='o3'; Tag='o3' },
  @{ Name='gemini-3.5-flash'; Safe='gemini-3.5-flash'; Tag='gemini35flash' }
)
$records = @()
foreach ($model in $models) {
  foreach ($setting in @('text_only', 'no_render', 'wrong_render')) {
    $input = "$InputDir\$($model.Tag)_$setting.jsonl"
    $manifest = "$Root\final_results_1200\$setting\$($model.Safe)\_manifest.csv"
    & $PythonExe eval/build_answer_input.py --tasks $Tasks --data-base . --manifest $manifest --output-jsonl $input --model $model.Name --setting $setting
    if ($LASTEXITCODE -ne 0) { throw "Input build failed: $($model.Name)/$setting" }
    $runName = "answer_complement600_$ts`_$($model.Tag)_$setting"
    $stdout = "$RunDir\$runName.out"; $stderr = "$RunDir\$runName.err"
    $args = @('-u','eval/answer_judge.py','--input-jsonl',$input,'--run-name',$runName,'--judge-model','gpt-5.4','--workers','1','--fast-exact')
    $p = Start-Process -FilePath $PythonExe -ArgumentList $args -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $records += [pscustomobject]@{model=$model.Name;setting=$setting;pid=$p.Id;run_name=$runName;input=$input;stdout=$stdout;stderr=$stderr}
    Write-Host "STARTED $($model.Name)/$setting pid=$($p.Id)"
  }
}
[pscustomobject]@{run_id=$ts;start_time=(Get-Date).ToString('o');total_workers=9;tasks=$Tasks;records=$records} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 "$RunDir\manifest.json"
Write-Host "MANIFEST $RunDir\manifest.json"
