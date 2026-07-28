@echo off
setlocal
cd /d "%~dp0\.."

if "%AZURE_STORAGE_SAS%"=="" (
  echo Missing AZURE_STORAGE_SAS. Run this first:
  echo   set AZURE_STORAGE_SAS=^<your SAS token^>
  exit /b 1
)

echo ============================================================
echo [1/4] Download reusable OLD real result dirs
echo       text_only + step1 wrong_render
echo ============================================================
python scripts\download_reusable_results_from_blob.py ^
  --settings text_only valid_wrong_render_step1 ^
  --models gpt-5.5 gemini-3.5-flash:stable o3 qwen3-vl-8b-thinking qwen3-vl-32b-thinking
if errorlevel 1 exit /b %errorlevel%

echo ============================================================
echo [2/4] Download NEWTASKS real result dirs from Blob
echo       text_cot + no_render + wrong_render
echo ============================================================
python scripts\download_newtasks_prefixes_from_blob.py --preset text_cot
if errorlevel 1 exit /b %errorlevel%

python scripts\download_newtasks_prefixes_from_blob.py --preset no_render
if errorlevel 1 exit /b %errorlevel%

python scripts\download_newtasks_prefixes_from_blob.py --preset wrong_render
if errorlevel 1 exit /b %errorlevel%

echo ============================================================
echo [3/4] Assemble final local 600-result directories
echo ============================================================
python scripts\assemble_final_results.py --settings text_only no_render wrong_render --overwrite
if errorlevel 1 exit /b %errorlevel%

echo ============================================================
echo [4/4] Check final assembled summary
echo ============================================================
type outputs\final_tracking\assembled_final_results_summary.csv
