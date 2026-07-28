#!/usr/bin/env bash
set -u -o pipefail

BASE="${SEE2THINK_BASE:-/root/autodl-tmp}"
PROJECT="$BASE/See2Think"
WATCH_LOG="${QWEN32_WATCH_LOG:-$BASE/setup_logs/qwen32_hourly_watchdog.log}"
PIPELINE_LOG="${QWEN32_PIPELINE_LOG:-$BASE/setup_logs/qwen32_full1200_direct.log}"
INTERVAL_SECONDS="${QWEN32_WATCH_INTERVAL_SECONDS:-3600}"
MODEL="qwen3-vl-32b-thinking"
WORKERS="${WORKERS:-3}"

mkdir -p "$(dirname "$WATCH_LOG")"
exec 9>"$BASE/setup_logs/qwen32_hourly_watchdog.lock"
if ! flock -n 9; then
  exit 0
fi

cd "$PROJECT"
source config.sh

log() {
  echo "[$(date '+%F %T %Z')] $*" >> "$WATCH_LOG"
}

batch_pids() {
  pgrep -f '^python -u solve/run_tasks.py .*qwen3-vl-32b-thinking' || true
}

solver_pids() {
  pgrep -f '^python solve/auto_solve.py .*qwen3-vl-32b-thinking' || true
}

pipeline_pids() {
  pgrep -f '^(bash )?(.*/)?scripts/qwen32_continue_after_smoke.sh$' || true
}

vllm_pid() {
  pgrep -f '^python3 -m vllm.entrypoints.openai.api_server --model .*/Qwen3-VL-32B-Thinking' | head -1 || true
}

vllm_healthy() {
  curl -fsS --max-time 20 \
    -H "Authorization: Bearer ${VLLM_API_KEY:-EMPTY}" \
    http://127.0.0.1:8000/health >/dev/null
}

stop_pipeline() {
  local pids
  pids="$(solver_pids)"
  [ -z "$pids" ] || kill -TERM $pids 2>/dev/null || true
  pids="$(batch_pids)"
  [ -z "$pids" ] || kill -TERM $pids 2>/dev/null || true
  pids="$(pipeline_pids)"
  [ -z "$pids" ] || kill -TERM $pids 2>/dev/null || true
  sleep 5
}

restart_vllm() {
  local pid engine
  pid="$(vllm_pid)"
  [ -z "$pid" ] || kill -TERM "$pid" 2>/dev/null || true
  sleep 10
  engine="$(pgrep -f '^VLLM::EngineCore$' || true)"
  [ -z "$engine" ] || kill -TERM $engine 2>/dev/null || true
  sleep 3

  export MODEL_PATH="$BASE/models/Qwen3-VL-32B-Thinking"
  export SERVED_MODEL_NAME="$MODEL"
  export VLLM_PORT=8000
  export CUDA_VISIBLE_DEVICES=0
  export TP_SIZE=1
  export GPU_MEMORY_UTILIZATION=0.90
  export MAX_MODEL_LEN=40960
  export MAX_NUM_SEQS=3
  export PATH="$BASE/venvs/vllm32/bin:$PATH"
  export SEE2THINK_LOG_DIR="$PROJECT/newlogs"

  log "restarting vLLM max_model_len=40960 max_num_seqs=3"
  if bash bin/start_vllm.sh >> "$WATCH_LOG" 2>&1; then
    log "vLLM restart succeeded"
    return 0
  fi
  log "ERROR vLLM restart failed"
  return 1
}

launch_pipeline() {
  log "launching/resuming full experiment workers=$WORKERS"
  nohup env WORKERS="$WORKERS" \
    "$PROJECT/scripts/qwen32_continue_after_smoke.sh" \
    >> "$PIPELINE_LOG" 2>&1 < /dev/null &
  log "pipeline supervisor started pid=$!"
}

log_progress() {
  local out task_dirs steps renders batches solvers
  out="$PROJECT/newtasks/final1200_qwen3-vl-32b-thinking_vaot_full"
  task_dirs=$(find "$out" -type f -name q.md -size +0c 2>/dev/null | wc -l)
  steps=$(find "$out" -type f -name steps.md -size +0c 2>/dev/null | wc -l)
  renders=$(find "$out" -type f \( -name 'p*.png' -o -name 'p*.jpg' -o -name 'p*.jpeg' \) ! -name 'p0.*' -size +0c 2>/dev/null | wc -l)
  batches=$(batch_pids | tr '\n' ',' | sed 's/,$//')
  solvers=$(solver_pids | tr '\n' ',' | sed 's/,$//')
  log "healthy progress task_dirs=$task_dirs steps=$steps renders=$renders batch_pids=${batches:-none} solver_pids=${solvers:-none}"
}

check_once() {
  if grep -q 'ALL_EXPERIMENTS_PROCESSED' "$PIPELINE_LOG" 2>/dev/null; then
    log "all experiments already complete; watchdog exiting"
    return 2
  fi

  if ! vllm_healthy; then
    log "ERROR vLLM health check failed; restarting service and pipeline"
    stop_pipeline
    if restart_vllm; then
      launch_pipeline
    fi
    return 0
  fi

  if [ -z "$(batch_pids)" ]; then
    log "WARNING no active batch process; waiting 120 seconds before restart"
    sleep 120
    if [ -z "$(batch_pids)" ]; then
      stop_pipeline
      launch_pipeline
      return 0
    fi
  fi

  log_progress
  return 0
}

log "hourly watchdog started interval=${INTERVAL_SECONDS}s workers=$WORKERS"
while true; do
  check_once
  status=$?
  [ "$status" -eq 2 ] && exit 0
  sleep "$INTERVAL_SECONDS"
done
