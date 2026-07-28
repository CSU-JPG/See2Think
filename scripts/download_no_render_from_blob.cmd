@echo off
setlocal
cd /d "%~dp0\.."

if "%AZURE_STORAGE_SAS%"=="" (
  echo Missing AZURE_STORAGE_SAS. Run:
  echo   set AZURE_STORAGE_SAS=^<your SAS token^>
  exit /b 1
)

python scripts\download_newtasks_prefixes_from_blob.py --preset no_render
python scripts\check_experiment_status.py

