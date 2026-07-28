#!/usr/bin/env bash
set -uo pipefail

B=/root/autodl-tmp
P="$B/See2Think"
VENV="$B/venvs/vllm013"
MODEL="$B/models/Qwen3-VL-8B-Thinking"
SETUP_LOG="$B/setup_logs"
PIPELINE_PID_FILE="$SETUP_LOG/qwen8_full_then_remaining_matrix.pid"
VLLM_PID_FILE="$SETUP_LOG/vllm8_server.pid"
PIPELINE_LOG="$SETUP_LOG/qwen8_full_then_remaining_matrix_resume_cap16k.log"
VLLM_LOG="$SETUP_LOG/vllm8_server_thinking32k_seq2_resume.log"
WATCH_LOG="$SETUP_LOG/qwen8_hourly_watchdog.log"
LOCK_FILE="$SETUP_LOG/qwen8_hourly_watchdog.lock"
PAUSE_FILE="$SETUP_LOG/qwen8.paused"
HEALTH_URL=http://127.0.0.1:8000/health

mkdir -p "$SETUP_LOG"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" >> "$WATCH_LOG"
}

pid_from_file_is_alive() {
  local file="$1" pid
  pid=$(cat "$file" 2>/dev/null || true)
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

vllm_healthy() {
  [[ "$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || true)" == "200" ]]
}

wait_for_vllm() {
  local i
  for i in $(seq 1 60); do
    if vllm_healthy; then
      return 0
    fi
    sleep 5
  done
  return 1
}

start_vllm() {
  local old_pid
  old_pid=$(cat "$VLLM_PID_FILE" 2>/dev/null || true)
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill -TERM "$old_pid" 2>/dev/null || true
    sleep 5
    kill -KILL "$old_pid" 2>/dev/null || true
  fi

  log "restarting vLLM"
  nohup "$VENV/bin/python" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name qwen3-vl-8b-thinking \
    --host 0.0.0.0 \
    --port 8000 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 32768 \
    --max-num-seqs 2 \
    >> "$VLLM_LOG" 2>&1 < /dev/null &
  echo $! > "$VLLM_PID_FILE"

  if wait_for_vllm; then
    log "vLLM recovered pid=$(cat "$VLLM_PID_FILE")"
    return 0
  fi

  log "ERROR vLLM failed to become healthy within 300 seconds"
  return 1
}

pipeline_is_alive() {
  if pid_from_file_is_alive "$PIPELINE_PID_FILE"; then
    return 0
  fi

  # Do not start a duplicate if the parent shell died but run_tasks survived.
  pgrep -f 'python -u solve/run_tasks.py.*qwen3-vl-8b-thinking' >/dev/null 2>&1
}

all_stages_complete() {
  grep -q 'ALL QWEN8 STAGES COMPLETE' "$PIPELINE_LOG" 2>/dev/null
}

start_pipeline() {
  log "restarting four-stage pipeline with START_POS=auto"
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
' >> "$PIPELINE_LOG" 2>&1 < /dev/null &

  echo $! > "$PIPELINE_PID_FILE"
  sleep 5
  if pipeline_is_alive; then
    log "pipeline recovered pid=$(cat "$PIPELINE_PID_FILE")"
    return 0
  fi

  log "ERROR pipeline did not stay alive after restart"
  return 1
}

log "hourly check started"

if [[ -e "$PAUSE_FILE" ]]; then
  log "experiment is manually paused; no health check or restart"
  exit 0
fi

if all_stages_complete; then
  log "all stages already complete; no action"
  exit 0
fi

if ! vllm_healthy; then
  log "vLLM unhealthy"
  start_vllm || exit 1
fi

if ! pipeline_is_alive; then
  log "pipeline not running"
  start_pipeline || exit 1
fi

pipeline_pid=$(cat "$PIPELINE_PID_FILE" 2>/dev/null || true)
vllm_pid=$(cat "$VLLM_PID_FILE" 2>/dev/null || true)
stage=$(grep -E '\] (START|DONE)|ALL QWEN' "$PIPELINE_LOG" 2>/dev/null | tail -n 1 || true)
progress=$(grep 'Progress:' "$PIPELINE_LOG" 2>/dev/null | tail -n 1 || true)
active=$(ps -C python -o cmd= 2>/dev/null | grep 'solve/auto_solve.py' | sed -n 's/.* -i \([0-9][0-9]*\) .*/\1/p' | paste -sd, - || true)
stats=$(awk '
/\] START / {success=0; failed=0; timeout=0; started=1; next}
started && /^Task completed:/ {success++}
started && /^Task failed:/ {failed++}
started && /^Task timeout after/ {failed++; timeout++}
started && /^Unexpected error:/ {failed++}
END {printf "success=%d failed=%d timeout=%d", success+0, failed+0, timeout+0}
' "$PIPELINE_LOG" 2>/dev/null || true)
disk=$(df -h "$B" | tail -n 1 | awk '{print $3" used, "$4" available, "$5}')
log "healthy pipeline_pid=$pipeline_pid vllm_pid=$vllm_pid stage=[$stage] active=${active:-none} stats=[$stats] progress=[$progress] disk=[$disk]"
