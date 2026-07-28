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

            if (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }

            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Import-ConfigSh "$Root\config.sh"

$PythonExe = (Get-Command python -ErrorAction Stop).Source
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

$RunDir = "$Root\newlogs\qwen3vl32b_acc_eval_1200_$ts"
$InputDir = "$Root\neweval\results\qwen3vl32b_acc_eval_1200_$ts\inputs"

New-Item -ItemType Directory -Force $RunDir, $InputDir | Out-Null

$modelName = "qwen3-vl-32b-instruct"
$modelSafe = "qwen3-vl-32b-instruct"
$modelTag = "qwen3vl32b"

$tasks = "json/tasks_see2thinkbench_1200task_available.json"

$settings = @(
    @{
        InputSetting = "text_cot"
        ResultSetting = "text_only"
    },
    @{
        InputSetting = "vaot_no_render"
        ResultSetting = "no_render"
    },
    @{
        InputSetting = "vaot_full"
        ResultSetting = "full"
    },
    @{
        InputSetting = "vaot_wrong_render"
        ResultSetting = "wrong_render"
    }
)

$records = @()

# ACC：四种 setting 全部进行答案正确率评测
foreach ($item in $settings) {
    $inputSetting = $item.InputSetting
    $resultSetting = $item.ResultSetting

    $input = "$InputDir\$modelTag`_$inputSetting.jsonl"
    $manifest = "$Root\final_results_1200\$resultSetting\$modelSafe\_manifest.csv"

    if (-not (Test-Path $manifest)) {
        throw "Manifest not found: $manifest. Run assemble_all_1200_results.py first."
    }

    & $PythonExe neweval/build_answer_input.py `
        --tasks $tasks `
        --data-base . `
        --manifest $manifest `
        --output-jsonl $input `
        --model $modelName `
        --setting $inputSetting

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build answer input for $modelName/$inputSetting"
    }

    $runName = "answer_qwen3vl32b_1200_$ts`_$inputSetting"
    $stdout = "$RunDir\$runName.out"
    $stderr = "$RunDir\$runName.err"

    $args = @(
        "-u",
        "neweval/answer_judge.py",
        "--input-jsonl", $input,
        "--run-name", $runName,
        "--judge-model", "gpt-5.4",
        "--workers", "1",
        "--fast-exact"
    )

    $p = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $args `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $records += [pscustomobject]@{
        type = "accuracy"
        model = $modelName
        setting = $inputSetting
        workers = 1
        pid = $p.Id
        run_name = $runName
        input = $input
        stdout = $stdout
        stderr = $stderr
    }

    Write-Host "STARTED accuracy $modelName/$inputSetting pid=$($p.Id)"
}

# Process Eval：只对 VAoT-Full 做过程指标评测
$evalRunName = "key_step_metric_qwen3vl32b_1200_$ts`_full"
$evalStdout = "$RunDir\$evalRunName.out"
$evalStderr = "$RunDir\$evalRunName.err"

$evalArgs = @(
    "-u",
    "neweval/key_step_metric_judge.py",
    "--tasks", $tasks,
    "--results-root", "final_results_1200/full",
    "--model", $modelSafe,
    "--run-name", $evalRunName,
    "--judge-model", "gpt-5.4",
    "--workers", "1"
)

$evalProcess = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList $evalArgs `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $evalStdout `
    -RedirectStandardError $evalStderr `
    -PassThru

$records += [pscustomobject]@{
    type = "process_eval"
    model = $modelName
    setting = "vaot_full"
    workers = 1
    pid = $evalProcess.Id
    run_name = $evalRunName
    input = $tasks
    stdout = $evalStdout
    stderr = $evalStderr
}

Write-Host "STARTED process eval $modelName/vaot_full pid=$($evalProcess.Id)"

[pscustomobject]@{
    run_id = $ts
    start_time = (Get-Date).ToString("o")
    total_workers = 5
    run_dir = $RunDir
    records = $records
} |
ConvertTo-Json -Depth 6 |
Set-Content -Encoding UTF8 "$RunDir\manifest.json"

Write-Host "MANIFEST $RunDir\manifest.json"