#!/usr/bin/env bash
set -euo pipefail

# Smoke test first, then run the full Qwen experiment matrix.
# Start vLLM before calling this script.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f config.sh ]]; then
  # shellcheck disable=SC1091
  source config.sh
fi

MODEL_LABEL="${MODEL_LABEL:-qwen3-vl-8b-thinking}"
REQUEST_MODEL="${REQUEST_MODEL:-$MODEL_LABEL}"
WORKERS="${WORKERS:-1}"
RUN_MODE="${RUN_MODE:-banana}"

SMOKE_SETTING="${SMOKE_SETTING:-vaot_full}"
SMOKE_TASKS="${SMOKE_TASKS:-json/tasks_see2thinkbench_1200task_available.json}"
SMOKE_START_POS="${SMOKE_START_POS:-0}"
SMOKE_END_POS="${SMOKE_END_POS:-5}"
SMOKE_OUTPUT_ROOT="${SMOKE_OUTPUT_ROOT:-$ROOT/smoke_test/${MODEL_LABEL}_${SMOKE_SETTING}_${SMOKE_START_POS}_${SMOKE_END_POS}}"

echo "============================================================"
echo "Smoke test before full matrix"
echo "  model label:   $MODEL_LABEL"
echo "  request model: $REQUEST_MODEL"
echo "  setting:       $SMOKE_SETTING"
echo "  tasks:         $SMOKE_TASKS"
echo "  range:         $SMOKE_START_POS..$SMOKE_END_POS"
echo "  output:        $SMOKE_OUTPUT_ROOT"
echo "============================================================"

MODEL_LABEL="$MODEL_LABEL" \
REQUEST_MODEL="$REQUEST_MODEL" \
SETTING="$SMOKE_SETTING" \
TASKS="$SMOKE_TASKS" \
START_POS="$SMOKE_START_POS" \
END_POS="$SMOKE_END_POS" \
OUTPUT_ROOT="$SMOKE_OUTPUT_ROOT" \
RUN_MODE="$RUN_MODE" \
WORKERS="$WORKERS" \
bash scripts/run_qwen1200_vllm.sh

echo
echo "Smoke test finished successfully. Starting full matrix."
echo

MODEL_LABEL="$MODEL_LABEL" \
REQUEST_MODEL="$REQUEST_MODEL" \
RUN_MODE="$RUN_MODE" \
WORKERS="$WORKERS" \
bash scripts/run_qwen_experiment_matrix.sh

