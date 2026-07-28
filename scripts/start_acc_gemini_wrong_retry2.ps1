Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING='utf-8'
$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
foreach($line in Get-Content "$Root\config.sh"){
  if($line -match '^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$'){
    [Environment]::SetEnvironmentVariable($Matches[1],($Matches[2] -replace '\s+#.*$','').Trim().Trim('"').Trim("'"),'Process')
  }
}
$PythonExe=(Get-Command python).Source
$ts=Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir="$Root\newlogs\acc_gemini_wrong_retry2_$ts"
$OutDir="$Root\neweval\results\acc_gemini_wrong_retry2_$ts"
New-Item -ItemType Directory -Force $RunDir,$OutDir | Out-Null
$tasks="$Root\json\tasks_gemini_wrong_retry2.json"
& $PythonExe scripts/build_selected_tasks.py --tasks json/tasks_see2thinkbench_complement600.json --keys 'emma/math::53' 'prism::72' --output $tasks
& $PythonExe neweval/build_answer_input.py --tasks $tasks --data-base . --manifest final_results_1200/wrong_render/gemini-3.5-flash/_manifest.csv --output-jsonl "$OutDir\input.jsonl" --model 'gemini-3.5-flash' --setting wrong_render
if($LASTEXITCODE -ne 0){throw 'Failed to build retry input'}
$runName="answer_gemini_wrong_retry2_$ts"
$p=Start-Process -FilePath $PythonExe -ArgumentList @('-u','neweval/answer_judge.py','--input-jsonl',"$OutDir\input.jsonl",'--run-name',$runName,'--judge-model','gpt-5.4','--workers','1','--fast-exact') -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput "$RunDir\$runName.out" -RedirectStandardError "$RunDir\$runName.err" -PassThru
[pscustomobject]@{run_name=$runName;pid=$p.Id;input="$OutDir\input.jsonl";output="$Root\neweval\results\$runName"}|ConvertTo-Json|Set-Content -Encoding UTF8 "$RunDir\manifest.json"
Write-Host "STARTED pid=$($p.Id) $runName"
