# Scripts guide

`scripts/` is intentionally kept flat because many PowerShell launchers call one another by their current paths. The groups below identify the maintained entrypoints; dated one-off runners are historical experiment helpers.

## Current experiment and evaluation entrypoints

- `run_remaining1200_one.ps1` — one model/setting worker for the complementary 600 tasks.
- `start_acc_and_eval_rerun.ps1` — starts ACC and evaluation reruns.
- `analyze_split_and_merged_1200.py` — produces separate 600-task and merged 1,200-task paper-style analyses.
- `export_merged_1200_evaluations.py` — exports merged 1,200-task evaluation records.
- `calculate_paired_interventions_1200.py` — computes paired Full/WrongRender intervention statistics.
- `export_paired_intervention_csvs_1200.py` — writes paired-intervention CSV tables.

## WrongRender quality audit

- `wrongrender_audit.py` — build, validate, summarize, and export audit data.
- `build_wrong_render_audit_packet_1200.py` — samples/builds audit packets from the 1,200-task outputs.
- `build_wrong_render_annotation_frontend.py` — creates the local audit frontend.
- `serve_wrong_render_audit.py` — serves the audit frontend locally.
- `export_wrong_render_audit_tasks_by_model.py` — exports audit task lists by model.

## Result assembly and maintenance

- `assemble_all_1200_results.py` / `assemble_final_results.py` — assemble final output directories.
- `check_experiment_status.py` — inspect run progress.
- `build_*tasks.py` — create selected, remaining, or retry task lists.
- `download_*` / `sync_*` — blob download and synchronization helpers.

## Historical scripts

Scripts named `final1154`, `final600`, `qwen*`, `watch_*`, or `*_retry*` record earlier runs. Keep them for reproducibility, but use the current entrypoints above for new work unless a specific historical reproduction is required.
