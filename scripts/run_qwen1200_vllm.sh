#!/usr/bin/env bash
set -euo pipefail

# Run Qwen3-VL 8B/32B through an OpenAI-compatible vLLM endpoint.
#
# Required before running:
#   1) Start vLLM and serve the model name used by REQUEST_MODEL.
#   2) Set GEMINI_API_KEY/GEMINI_BASE_URL because the current renderer path
#      initializes the Nano-Banana/Gemini image client even for text/no-render.
#   3) Ensure annotation/dataset/data is present under this project root.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f config.sh ]]; then
  # shellcheck disable=SC1091
  source config.sh
fi

MODEL_LABEL="${MODEL_LABEL:-qwen3-vl-8b-thinking}"
REQUEST_MODEL="${REQUEST_MODEL:-$MODEL_LABEL}"
SETTING="${SETTING:-vaot_full}"
TASKS="${TASKS:-json/tasks_see2thinkbench_1200task_available.json}"
START_POS="${START_POS:-auto}"
END_POS="${END_POS:-}"
WORKERS="${WORKERS:-1}"
RUN_MODE="${RUN_MODE:-banana}"
PROMPT_DIR="${PROMPT_DIR:-prompt}"
OUTPUT_TAG="${OUTPUT_TAG:-final1200}"
TASK_TIMEOUT="${SEE2THINK_TASK_TIMEOUT_SECONDS:-1200}"

case "$SETTING" in
  text_cot|vaot_no_render|vaot_full|vaot_wrong_render) ;;
  *)
    echo "Unsupported SETTING=$SETTING. Use text_cot, vaot_no_render, vaot_full, or vaot_wrong_render." >&2
    exit 2
    ;;
esac

export SKIP_CONFIRM=1
export SEE2THINK_DATA_BASE="${SEE2THINK_DATA_BASE:-$ROOT}"
export SEE2THINK_LLM_BACKEND="${SEE2THINK_LLM_BACKEND:-vllm}"
export VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export VLLM_API_KEY="${VLLM_API_KEY:-EMPTY}"
export SEE2THINK_REQUEST_MODEL="$REQUEST_MODEL"
export SEE2THINK_TASK_TIMEOUT_SECONDS="$TASK_TIMEOUT"

SAFE_MODEL="${MODEL_LABEL//[:\/\\]/_}"
export SEE2THINK_OUTPUT_BASE="${OUTPUT_ROOT:-$ROOT/newtasks/${OUTPUT_TAG}_${SAFE_MODEL}_${SETTING}}"
export SEE2THINK_LOG_DIR="${LOG_ROOT:-$ROOT/newlogs/${OUTPUT_TAG}_${SAFE_MODEL}_${SETTING}}"
mkdir -p "$SEE2THINK_OUTPUT_BASE" "$SEE2THINK_LOG_DIR"

SUBDIR="${RUN_MODE}_${MODEL_LABEL}_${SETTING}"
if [[ "$START_POS" == "auto" ]]; then
  FIND_ARGS=(--tasks "$TASKS" --output-root "$SEE2THINK_OUTPUT_BASE" --subdir "$SUBDIR")
  if [[ "$SETTING" == "vaot_full" || "$SETTING" == "vaot_wrong_render" ]]; then
    FIND_ARGS+=(--require-render)
  fi
  START_POS="$(python scripts/find_next_start.py "${FIND_ARGS[@]}")"
fi
if [[ -z "$END_POS" ]]; then
  END_POS="$(python -c "import json; print(len(json.load(open('$TASKS', encoding='utf-8'))))")"
fi

echo "============================================================"
echo "Qwen run"
echo "  model label:     $MODEL_LABEL"
echo "  request model:   $REQUEST_MODEL"
echo "  setting:         $SETTING"
echo "  tasks:           $TASKS"
echo "  range:           $START_POS..$END_POS"
echo "  workers:         $WORKERS"
echo "  run mode:        $RUN_MODE"
echo "  vLLM base:       $VLLM_BASE_URL"
echo "  output:          $SEE2THINK_OUTPUT_BASE"
echo "  logs:            $SEE2THINK_LOG_DIR"
echo "============================================================"

python -u solve/run_tasks.py \
  --tasks "$TASKS" \
  --mode "$RUN_MODE" \
  --model "$MODEL_LABEL" \
  --workers "$WORKERS" \
  --start "$START_POS" \
  --end "$END_POS" \
  --setting "$SETTING" \
  --prompt_dir "$PROMPT_DIR"
