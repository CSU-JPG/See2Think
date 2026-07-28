#!/usr/bin/env bash
set -euo pipefail

# Exact Qwen experiment matrix:
#   text_cot:          600 tasks
#   vaot_no_render:    600 tasks
#   vaot_wrong_render: 600 tasks
#   vaot_full:        1200 tasks
#
# Run once per served model. Start vLLM first, then call this script with
# MODEL_LABEL and REQUEST_MODEL matching the served model name.

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

TASKS_600="${TASKS_600:-json/tasks_see2thinkbench_600_no_gpt5_step1.json}"
TASKS_1200="${TASKS_1200:-json/tasks_see2thinkbench_1200task_available.json}"

run_one() {
  local setting="$1"
  local tasks="$2"
  local tag="$3"
  echo
  echo "==================== $MODEL_LABEL $setting ===================="
  MODEL_LABEL="$MODEL_LABEL" \
  REQUEST_MODEL="$REQUEST_MODEL" \
  SETTING="$setting" \
  TASKS="$tasks" \
  OUTPUT_TAG="$tag" \
  RUN_MODE="$RUN_MODE" \
  WORKERS="$WORKERS" \
  bash scripts/run_qwen1200_vllm.sh
}

run_one text_cot "$TASKS_600" final600
run_one vaot_no_render "$TASKS_600" final600
run_one vaot_wrong_render "$TASKS_600" final600
run_one vaot_full "$TASKS_1200" final1200

echo
echo "Qwen matrix finished for $MODEL_LABEL"
