# Task manifest example

See2Think experiment entrypoints take a task manifest with `--tasks`.

The public repository does not include the paper's full task manifests or benchmark images. Put your local data wherever convenient, then create a JSON list with the same structure as `tasks.example.json`.

Required fields:

- `path`: path to a benchmark `data.json` file, relative to `--data-base` / `SEE2THINK_DATA_BASE`.
- `id`: integer index of the sample inside that `data.json`.
- `category`: coarse task group, usually `2D`, `3D`, or `Real`.
- `target_task`: task-family name used for grouping.

Example run:

```bash
python -u solve/run_tasks.py \
  --tasks examples/tasks.example.json \
  --mode banana \
  --model gpt-5.5 \
  --setting vaot_full \
  --workers 1 \
  --prompt_dir prompt
```

The example manifest is for format reference; replace its paths with real local data paths before running a full experiment.
