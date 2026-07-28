#!/usr/bin/env bash
set -u

B="/root/autodl-tmp"
P="$B/See2Think"
VENV="$B/venvs/vllm013"
MODEL="$B/models/Qwen3-VL-8B-Thinking"
SETUP_LOG="$B/setup_logs"
PIPELINE_LOG="$SETUP_LOG/qwen8_full_then_remaining_matrix_resume_cap16k.log"
WATCH_LOG="$SETUP_LOG/qwen8_hourly_supervisor.log"
INTERVAL_SECONDS="${QWEN8_WATCH_INTERVAL_SECONDS:-3600}"
HEALTH_URL="http://127.0.0.1:8000/health"
PAUSE_FILE="$SETUP_LOG/qwen8.paused"

mkdir -p "$SETUP_LOG"
exec >>"$WATCH_LOG" 2>&1
exec 9>"$SETUP_LOG/qwen8_hourly_supervisor.lock"
if ! flock -n 9; then
  echo "[$(date -Is)] another supervisor instance already holds the lock"
  exit 0
fi

log() {
  echo "[$(date -Is)] $*"
}

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

vllm_healthy() {
  curl -fsS -m 5 "$HEALTH_URL" >/dev/null 2>&1
}

pipeline_complete() {
  grep -q 'ALL QWEN8 STAGES COMPLETE' "$PIPELINE_LOG" 2>/dev/null
}

start_vllm() {
  local old_pid new_pid
  old_pid="$(cat "$SETUP_LOG/vllm8_server.pid" 2>/dev/null || true)"
  if pid_alive "$old_pid"; then
    log "vLLM pid=$old_pid exists but health failed; terminating it"
    kill -TERM "$old_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      pid_alive "$old_pid" || break
      sleep 1
    done
    pid_alive "$old_pid" && kill -KILL "$old_pid" 2>/dev/null || true
  fi

  log "starting vLLM: official Thinking, context=32768, max_num_seqs=2"
  nohup "$VENV/bin/python" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name qwen3-vl-8b-thinking \
    --host 0.0.0.0 \
    --port 8000 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 32768 \
    --max-num-seqs 2 \
    >>"$SETUP_LOG/vllm8_server_thinking32k_seq2_supervised.log" 2>&1 < /dev/null &
  new_pid=$!
  echo "$new_pid" >"$SETUP_LOG/vllm8_server.pid"

  for _ in $(seq 1 60); do
    if vllm_healthy; then
      log "vLLM recovered pid=$new_pid health=200"
      return 0
    fi
    pid_alive "$new_pid" || break
    sleep 2
  done

  log "ERROR: vLLM failed to become healthy pid=$new_pid"
  return 1
}

start_pipeline() {
  local pipeline_pid
  log "starting four-stage pipeline with START_POS=auto workers=2 max_tokens=16384"
  cd "$P" || return 1
  nohup env \
    PATH="$VENV/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    MODEL_LABEL=qwen3-vl-8b-thinking \
    REQUEST_MODEL=qwen3-vl-8b-thinking \
    WORKERS=2 \
    RUN_MODE=banana \
    SEE2THINK_TASK_TIMEOUT_SECONDS=1200 \
    SEE2THINK_MAX_TOKENS=16384 \
    SEE2THINK_BACKEND_HEALTH_URL="$HEALTH_URL" \
    SEE2THINK_BACKEND_HEALTH_POLL_SECONDS=5 \
    bash -c '
set -euo pipefail
cd /root/autodl-tmp/See2Think
run_stage() {
  local setting="$1" tasks="$2" tag="$3"
  echo "[$(date -Is)] START $setting tasks=$tasks tag=$tag workers=$WORKERS max_tokens=$SEE2THINK_MAX_TOKENS"
  SETTING="$setting" TASKS="$tasks" OUTPUT_TAG="$tag" START_POS=auto bash scripts/run_qwen1200_vllm.sh
  echo "[$(date -Is)] DONE $setting"
}
run_stage vaot_full json/tasks_see2thinkbench_1200task_available.json final1200
run_stage text_cot json/tasks_see2thinkbench_600_no_gpt5_step1.json final600
run_stage vaot_no_render json/tasks_see2thinkbench_600_no_gpt5_step1.json final600
run_stage vaot_wrong_render json/tasks_see2thinkbench_600_no_gpt5_step1.json final600
echo "[$(date -Is)] ALL QWEN8 STAGES COMPLETE"
' >>"$PIPELINE_LOG" 2>&1 < /dev/null &
  pipeline_pid=$!
  echo "$pipeline_pid" >"$SETUP_LOG/qwen8_full_then_remaining_matrix.pid"
  sleep 3
  if pid_alive "$pipeline_pid"; then
    log "pipeline recovered pid=$pipeline_pid"
    return 0
  fi
  log "ERROR: pipeline failed to stay running pid=$pipeline_pid"
  return 1
}

check_once() {
  local pipeline_pid vllm_pid active stage stats progress disk
  log "hourly check begin"

  if [[ -e "$PAUSE_FILE" ]]; then
    log "experiment is manually paused; no health check or restart"
    return 0
  fi

  if pipeline_complete; then
    log "all four Qwen8 stages are complete; no restart required"
    return 0
  fi

  vllm_pid="$(cat "$SETUP_LOG/vllm8_server.pid" 2>/dev/null || true)"
  if vllm_healthy; then
    log "vLLM healthy pid=$vllm_pid"
  else
    log "vLLM unhealthy pid=$vllm_pid"
    start_vllm || return 1
  fi

  pipeline_pid="$(cat "$SETUP_LOG/qwen8_full_then_remaining_matrix.pid" 2>/dev/null || true)"
  if pid_alive "$pipeline_pid"; then
    log "pipeline healthy pid=$pipeline_pid"
  else
    log "pipeline stopped pid=$pipeline_pid"
    start_pipeline || return 1
    pipeline_pid="$(cat "$SETUP_LOG/qwen8_full_then_remaining_matrix.pid" 2>/dev/null || true)"
  fi

  active="$(ps -C python -o cmd= | grep 'solve/auto_solve.py' | sed -n 's/.* -i \([0-9][0-9]*\) .*/\1/p' | paste -sd, - || true)"
  stage="$(grep -E '\] (START|DONE)|ALL QWEN' "$PIPELINE_LOG" 2>/dev/null | tail -n 1 || true)"
  stats="$(awk '
/\] START / {success=0; failed=0; timeout=0; started=1; next}
started && /^Task completed:/ {success++}
started && /^Task failed:/ {failed++}
started && /^Task timeout after/ {failed++; timeout++}
started && /^Unexpected error:/ {failed++}
END {printf "success=%d failed=%d timeout=%d", success+0, failed+0, timeout+0}
' "$PIPELINE_LOG" 2>/dev/null || true)"
  progress="$(grep 'Progress:' "$PIPELINE_LOG" 2>/dev/null | tail -n 1 || true)"
  disk="$(df -h "$B" | tail -n 1 | awk '{print $3" used, "$4" available, "$5}')"
  log "stage=[$stage]; active=${active:-none}; $stats; ${progress:-progress unavailable}; disk=$disk"
  log "hourly check end"
}

if [[ "${1:-}" == "--once" ]]; then
  check_once
  exit $?
fi

echo $$ >"$SETUP_LOG/qwen8_hourly_supervisor.pid"
log "supervisor started interval=${INTERVAL_SECONDS}s pid=$$"
while true; do
  check_once || log "ERROR: check failed; will retry next interval"
  sleep "$INTERVAL_SECONDS"
done
