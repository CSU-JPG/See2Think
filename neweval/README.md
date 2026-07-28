# See2Think Process Judge

This directory contains the process-level judge pipeline for See2ThinkBench.

The judge evaluates one VAoT-Full trajectory with one model call and returns three scores:

- `action_relevance`
- `render_faithfulness`
- `feedback_uptake`

Each score is already normalized: `0`, `0.5`, or `1`.

## Dry Run

```bash
cd /storage/v-jinpewang/yansiyu_workspace/See2Think
source config.sh

python -u neweval/process_judge.py \
  --tasks json/tasks_see2thinkbench_600_no_gpt5_step1.json \
  --results-root newtasks/gpt-5_12task_vaot_full \
  --model gpt-5 \
  --setting vaot_full \
  --judge-model gpt-5 \
  --run-name debug_gpt5_full \
  --limit 2 \
  --dry-run
```

## Real Run

```bash
cd /storage/v-jinpewang/yansiyu_workspace/See2Think
source config.sh

python -u neweval/process_judge.py \
  --tasks json/tasks_see2thinkbench_600_no_gpt5_step1.json \
  --results-root newtasks/qwen3-vl-8b-thinking_600_vaot_full \
  --model qwen3-vl-8b-thinking \
  --setting vaot_full \
  --judge-model gpt-5 \
  --run-name qwen8b_600_vaot_full_process_judge \
  --workers 1
```

Outputs are written to:

```text
neweval/results/<run-name>/process_judge.jsonl
neweval/results/<run-name>/process_judge.csv
neweval/results/<run-name>/summary.json
neweval/results/<run-name>/failures.jsonl
```

Use `--no-images` if you want a text-only judge call. Keeping images enabled is recommended for `render_faithfulness`.
