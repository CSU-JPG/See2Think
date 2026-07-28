#!/usr/bin/env bash
set -euo pipefail

BASE="${SEE2THINK_BASE:-/root/autodl-tmp}"
PROJECT="$BASE/See2Think"
cd "$PROJECT"
source config.sh
export PATH="$BASE/venvs/see2think/bin:$PATH"

MODEL="${MODEL_LABEL:-qwen3-vl-32b-thinking}"
TASKS1200="${TASKS1200:-json/tasks_see2thinkbench_1200task_available.json}"
WORKERS="${WORKERS:-3}"
FIVE="$PROJECT/smoke_test/${MODEL}_vaot_full_retry5"

log() { echo "[$(date '+%F %T %Z')] $*"; }

steps=$(find "$FIVE" -type f -name steps.md -size +0c 2>/dev/null | wc -l)
renders=$(find "$FIVE" -type f \( -name 'p*.png' -o -name 'p*.jpg' -o -name 'p*.jpeg' \) ! -name 'p0.*' -size +0c 2>/dev/null | wc -l)
if [ "$steps" -lt 5 ] || [ "$renders" -lt 5 ]; then
  log "WARNING five-task smoke has failed/incomplete samples steps=$steps renders=$renders; continuing"
fi
log "SMOKE_TEST_PROCESSED steps=$steps renders=$renders"

log "starting formal vaot_full 1200"
MODEL_LABEL="$MODEL" REQUEST_MODEL="$MODEL" SETTING=vaot_full TASKS="$TASKS1200" OUTPUT_TAG=final1200 WORKERS="$WORKERS" \
  bash scripts/run_qwen1200_vllm.sh
log "FULL_1200_PROCESSED"

log "starting remaining experiment matrix"
MODEL_LABEL="$MODEL" REQUEST_MODEL="$MODEL" WORKERS="$WORKERS" \
  bash scripts/run_qwen_experiment_matrix.sh
log "ALL_EXPERIMENTS_PROCESSED"
