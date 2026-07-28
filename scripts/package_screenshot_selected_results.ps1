param(
    [string]$PackageName = "selected_model_results_23_20260714_final"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$exportRoot = Join-Path $repoRoot "exports"
$stageRoot = Join-Path $exportRoot $PackageName
$zipPath = Join-Path $exportRoot "$PackageName.zip"

function Get-RelativeChildPath {
    param([string]$BasePath, [string]$ChildPath)

    $baseFull = [IO.Path]::GetFullPath($BasePath).TrimEnd("\") + "\"
    $childFull = [IO.Path]::GetFullPath($ChildPath)
    if (-not $childFull.StartsWith($baseFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is not inside base directory: $childFull"
    }
    return $childFull.Substring($baseFull.Length)
}

if (Test-Path -LiteralPath $stageRoot) {
    throw "Staging directory already exists: $stageRoot"
}
if (Test-Path -LiteralPath $zipPath) {
    throw "ZIP already exists: $zipPath"
}

$items = @(
    [pscustomobject]@{ UiIndex = 400;  Model = "gemini-3.5-flash"; FamilyPath = "m3cot\test1";    TaskKey = "m3cot/test1";    SampleId = "0";  Evidence = "user_confirmed_gemini" },
    [pscustomobject]@{ UiIndex = 451;  Model = "gpt-5.5";                 FamilyPath = "m3cot\test1";    TaskKey = "m3cot/test1";    SampleId = "51"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 460;  Model = "o3";                      FamilyPath = "m3cot\test1";    TaskKey = "m3cot/test1";    SampleId = "60"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 513;  Model = "gemini-3.5-flash"; FamilyPath = "prism";          TaskKey = "prism";          SampleId = "13"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 519;  Model = "gpt-5.5";                 FamilyPath = "prism";          TaskKey = "prism";          SampleId = "19"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 532;  Model = "o3";                      FamilyPath = "prism";          TaskKey = "prism";          SampleId = "32"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 600;  Model = "gemini-3.5-flash"; FamilyPath = "clevr_math\val"; TaskKey = "clevr_math/val"; SampleId = "0";  Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 615;  Model = "gemini-3.5-flash"; FamilyPath = "clevr_math\val"; TaskKey = "clevr_math/val"; SampleId = "15"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 655;  Model = "o3";                      FamilyPath = "clevr_math\val"; TaskKey = "clevr_math/val"; SampleId = "55"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 723;  Model = "gemini-3.5-flash"; FamilyPath = "super_clevr";    TaskKey = "super_clevr";    SampleId = "23"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 751;  Model = "gemini-3.5-flash"; FamilyPath = "super_clevr";    TaskKey = "super_clevr";    SampleId = "51"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 777;  Model = "gpt-5.5";                 FamilyPath = "super_clevr";    TaskKey = "super_clevr";    SampleId = "77"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 847;  Model = "gpt-5.5";                 FamilyPath = "VLABench";       TaskKey = "VLABench";       SampleId = "47"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 894;  Model = "o3";                      FamilyPath = "DROID";          TaskKey = "DROID";          SampleId = "1";  Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 898;  Model = "o3";                      FamilyPath = "DROID";          TaskKey = "DROID";          SampleId = "5";  Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 926;  Model = "gemini-3.5-flash"; FamilyPath = "DROID";          TaskKey = "DROID";          SampleId = "33"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 984;  Model = "gemini-3.5-flash"; FamilyPath = "m3cot\test0";    TaskKey = "m3cot/test0";    SampleId = "2";  Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 989;  Model = "gemini-3.5-flash"; FamilyPath = "m3cot\test0";    TaskKey = "m3cot/test0";    SampleId = "7";  Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 1011; Model = "o3";                      FamilyPath = "m3cot\test0";    TaskKey = "m3cot/test0";    SampleId = "29"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 1061; Model = "gpt-5.5";                 FamilyPath = "intphy2";        TaskKey = "intphy2";        SampleId = "7";  Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 1085; Model = "gemini-3.5-flash"; FamilyPath = "intphy2";        TaskKey = "intphy2";        SampleId = "31"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 1086; Model = "gemini-3.5-flash"; FamilyPath = "intphy2";        TaskKey = "intphy2";        SampleId = "32"; Evidence = "right_panel_model_label" },
    [pscustomobject]@{ UiIndex = 1158; Model = "o3";                      FamilyPath = "m3cot\test0";    TaskKey = "m3cot/test0";    SampleId = "76"; Evidence = "right_panel_model_label" }
)

New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
$resultsRoot = Join-Path $stageRoot "results"
New-Item -ItemType Directory -Path $resultsRoot -Force | Out-Null

$manifest = foreach ($item in $items) {
    $sourceDir = Join-Path (Join-Path (Join-Path $repoRoot "final_results\full") $item.Model) (Join-Path $item.FamilyPath $item.SampleId)
    if (-not (Test-Path -LiteralPath $sourceDir -PathType Container)) {
        throw "Missing selected result directory: $sourceDir"
    }

    $safeTask = $item.TaskKey -replace "[/\\]", "_"
    $caseName = "{0:D4}_{1}_{2}" -f $item.UiIndex, $safeTask, $item.SampleId
    $packageDir = Join-Path (Join-Path $resultsRoot $caseName) $item.Model
    New-Item -ItemType Directory -Path $packageDir -Force | Out-Null
    Copy-Item -Path (Join-Path $sourceDir "*") -Destination $packageDir -Recurse -Force

    $files = @(Get-ChildItem -LiteralPath $packageDir -Recurse -File)
    [pscustomobject]@{
        ui_index = $item.UiIndex
        task = "$($item.TaskKey)::$($item.SampleId)"
        selected_model = $item.Model
        selection_evidence = $item.Evidence
        source_relative_path = Get-RelativeChildPath $repoRoot $sourceDir
        package_relative_path = Get-RelativeChildPath $stageRoot $packageDir
        file_count = $files.Count
        total_bytes = ($files | Measure-Object -Property Length -Sum).Sum
    }
}

$manifest | Export-Csv -LiteralPath (Join-Path $stageRoot "manifest.csv") -NoTypeInformation -Encoding UTF8
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stageRoot "manifest.json") -Encoding UTF8

$checksums = foreach ($file in Get-ChildItem -LiteralPath $resultsRoot -Recurse -File | Sort-Object FullName) {
    [pscustomobject]@{
        relative_path = Get-RelativeChildPath $stageRoot $file.FullName
        size_bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$checksums | Export-Csv -LiteralPath (Join-Path $stageRoot "checksums_sha256.csv") -NoTypeInformation -Encoding UTF8

$readme = @"
Selected model results from 23 screenshots

- Each results/<case>/<model>/ directory contains exactly the one model selected in the screenshot.
- Source setting: final_results/full
- Models: gpt-5.5 (5), o3 (7), gemini-3.5-flash (11)
- Original result files: 98
- #400 uses gemini-3.5-flash, as confirmed by the user.
- manifest.csv/json records every mapping and source path.
- checksums_sha256.csv records the SHA-256 of every copied result file.
"@
$readme | Set-Content -LiteralPath (Join-Path $stageRoot "README.txt") -Encoding UTF8

Compress-Archive -LiteralPath $stageRoot -DestinationPath $zipPath -CompressionLevel Optimal

$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
[pscustomobject]@{
    package_directory = $stageRoot
    zip_path = $zipPath
    selected_cases = $manifest.Count
    result_files = $checksums.Count
    source_bytes = ($manifest | Measure-Object -Property total_bytes -Sum).Sum
    zip_bytes = (Get-Item -LiteralPath $zipPath).Length
    zip_sha256 = $zipHash
} | ConvertTo-Json -Depth 3
