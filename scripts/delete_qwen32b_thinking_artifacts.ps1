Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Root = (Resolve-Path -LiteralPath $Root).Path
Set-Location $Root

function Add-Existing {
  param(
    [System.Collections.Generic.List[object]]$Targets,
    [string]$Pattern
  )
  $items = Get-ChildItem -Path $Pattern -Force -ErrorAction SilentlyContinue
  foreach ($item in $items) {
    if ($item) { $Targets.Add($item) }
  }
}

$targets = [System.Collections.Generic.List[object]]::new()

Add-Existing $targets "newtasks\final1200_qwen3-vl-32b-thinking*"
Add-Existing $targets "newtasks\smoke_qwen3vl32b_full_*"
Add-Existing $targets "newtasks\smoke3_qwen3-vl-32b-thinking*"
Add-Existing $targets "newtasks\test100_qwen3-vl-32b-thinking*"
Add-Existing $targets "newlogs\final1200_qwen3-vl-32b-thinking*"
Add-Existing $targets "newlogs\smoke_qwen3vl32b_full_*"
Add-Existing $targets "newlogs\smoke3_qwen3-vl-32b-thinking*"
Add-Existing $targets "newlogs\test100_qwen3-vl-32b-thinking*"
Add-Existing $targets "outputs\qwen3vl32b_failure_tracking"

$statusDirs = Get-ChildItem -Path "newlogs\qwen3vl32b_status_*" -Directory -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -notlike "qwen3vl32b_instruct_status_*" }
foreach ($dir in $statusDirs) { $targets.Add($dir) }

$apiDirs = Get-ChildItem -Path "newlogs\qwen3vl32b_api_*" -Directory -Force -ErrorAction SilentlyContinue
foreach ($dir in $apiDirs) {
  $delete = $false
  $manifest = Join-Path $dir.FullName "manifest.json"
  if (Test-Path -LiteralPath $manifest) {
    try {
      $j = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
      if (($j.model -eq "qwen3-vl-32b-thinking") -or ($j.request_model -eq "qwen3-vl-32b-thinking")) {
        $delete = $true
      }
    } catch {
      $delete = $false
    }
  } elseif ($dir.Name -match "qwen3vl32b_api_1200_|qwen3vl32b_api_1200_monitor|qwen3vl32b_api_full100_|qwen3vl32b_api_smoke3_") {
    $delete = $true
  }
  if ($delete) { $targets.Add($dir) }
}

$targets = @($targets | Sort-Object FullName -Unique)

foreach ($target in $targets) {
  $full = $target.FullName
  if (-not $full.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to delete outside workspace: $full"
  }
  if ($full -match "qwen3-vl-32b-instruct|qwen3vl32b_instruct_status|20260723_202928|20260723_202929|20260723_202932") {
    throw "Refusing to delete current Instruct path: $full"
  }
}

$bytes = 0L
foreach ($target in $targets) {
  if ($target.PSIsContainer) {
    $sum = Get-ChildItem -LiteralPath $target.FullName -Recurse -Force -File -ErrorAction SilentlyContinue |
      Measure-Object -Property Length -Sum
    if ($null -ne $sum -and $null -ne $sum.Sum) { $bytes += [int64]$sum.Sum }
  } else {
    $bytes += [int64]$target.Length
  }
}

foreach ($target in $targets) {
  Remove-Item -LiteralPath $target.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

[pscustomobject]@{
  deleted_count = $targets.Count
  approx_deleted_mb = [math]::Round($bytes / 1MB, 2)
}
