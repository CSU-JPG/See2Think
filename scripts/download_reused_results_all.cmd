@echo off
setlocal
cd /d "%~dp0\.."

if "%AZURE_STORAGE_SAS%"=="" (
  echo Missing AZURE_STORAGE_SAS. Run:
  echo   set AZURE_STORAGE_SAS=^<your SAS token^>
  exit /b 1
)

python scripts\download_reusable_results_from_blob.py ^
  --settings text_only valid_wrong_render_step1 optional_with_generated_image

