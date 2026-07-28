Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
foreach ($line in Get-Content -LiteralPath "$Root\config.sh") {
  if ($line -match '^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
    [Environment]::SetEnvironmentVariable($Matches[1], ($Matches[2] -replace '\s+#.*$', '').Trim().Trim('"').Trim("'"), 'Process')
  }
}
$PythonExe = (Get-Command python -ErrorAction Stop).Source
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = "$Root\newlogs\acc_complement600_fix_$ts"
$InputDir = "$Root\neweval\results\acc_complement600_fix_$ts\inputs"
$Tasks = "$Root\json\tasks_see2thinkbench_complement600.json"
New-Item -ItemType Directory -Force $RunDir, $InputDir | Out-Null
$jobs = @(
  @{Name='o3';Safe='o3';Tag='o3';Setting='text_only'},
  @{Name='gemini-3.5-flash';Safe='gemini-3.5-flash';Tag='gemini35flash';Setting='wrong_render'}
)
$records=@()
foreach($job in $jobs){
  $input="$InputDir\$($job.Tag)_$($job.Setting).jsonl"
  $manifest="$Root\final_results_1200\$($job.Setting)\$($job.Safe)\_manifest.csv"
  & $PythonExe neweval/build_answer_input.py --tasks $Tasks --data-base . --manifest $manifest --output-jsonl $input --model $job.Name --setting $job.Setting
  if($LASTEXITCODE -ne 0){throw "Input build failed"}
  $runName="answer_complement600_$ts`_$($job.Tag)_$($job.Setting)"
  $stdout="$RunDir\$runName.out";$stderr="$RunDir\$runName.err"
  $args=@('-u','neweval/answer_judge.py','--input-jsonl',$input,'--run-name',$runName,'--judge-model','gpt-5.4','--workers','1','--fast-exact')
  $p=Start-Process -FilePath $PythonExe -ArgumentList $args -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  $records += [pscustomobject]@{model=$job.Name;setting=$job.Setting;pid=$p.Id;run_name=$runName;input=$input;stdout=$stdout;stderr=$stderr}
  Write-Host "STARTED $($job.Name)/$($job.Setting) pid=$($p.Id)"
}
[pscustomobject]@{run_id=$ts;tasks=$Tasks;records=$records}|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 "$RunDir\manifest.json"
