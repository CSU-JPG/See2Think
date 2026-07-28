#!/usr/bin/env bash

# Launch a local experiment that wires vLLM (Qwen3-VL) as the chat backend
# and the local Qwen Image Edit server for image generation/editing.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

#############################
# Configurable environment. #
#############################

# vLLM (Qwen3-VL) settings
VLLM_MODEL="${VLLM_MODEL:-Qwen/Qwen3-VL-8B-Thinking-GGUF}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8110}"
LOCAL_VLLM_API_KEY="${LOCAL_VLLM_API_KEY:-local-qwen}"
VLLM_LOG="${VLLM_LOG:-${LOG_DIR}/vllm_qwen3_${TIMESTAMP}.log}"

# Local Qwen Image Edit service settings
QWEN_IMAGE_HOST="${QWEN_IMAGE_HOST:-127.0.0.1}"
QWEN_IMAGE_PORT="${QWEN_IMAGE_PORT:-8210}"
QWEN_IMAGE_LOG="${QWEN_IMAGE_LOG:-${LOG_DIR}/qwen_image_edit_${TIMESTAMP}.log}"

# Task runner configuration
TASKS_FILE="${TASKS_FILE:-json/tasks_annotation_dataset_data_emma_chemistry_data.json}"
TASK_START="${TASK_START:-0}"
TASK_END="${TASK_END:-30}"
RUN_MODE="${RUN_MODE:-qwen}"
# Default model label matches the basename of the vLLM model (e.g. Qwen3-VL-8B-Thinking-GGUF)
DEFAULT_RUN_MODEL_NAME="${VLLM_MODEL##*/}"
RUN_MODEL_NAME="${RUN_MODEL_NAME:-$DEFAULT_RUN_MODEL_NAME}"
RUN_WORKERS="${RUN_WORKERS:-30}"
RUN_LINEAR="${RUN_LINEAR:-false}"
RUN_EXPERIMENT="${RUN_EXPERIMENT:-false}"
RUN_EXPERIMENT_TYPES="${RUN_EXPERIMENT_TYPES:-}"
RUN_GLOBAL_PARALLEL="${RUN_GLOBAL_PARALLEL:-false}"

#########################
# Basic sanity checks.  #
#########################

require_bin() {
	if ! command -v "$1" >/dev/null 2>&1; then
		echo "Missing required binary: $1" >&2
		exit 1
	fi
}

require_bin python
require_bin vllm
require_bin curl

for var in GEMINI_API_KEY GEMINI_BASE_URL; do
	if [[ -z "${!var:-}" ]]; then
		echo "Environment variable $var must be set (see config.example.sh)." >&2
		exit 1
	fi
done

#########################
# Helper functionality. #
#########################

wait_for_http() {
	local url="$1"
	local label="$2"
	local timeout="${3:-120}"
	local interval=2
	local elapsed=0
	printf "Waiting for %s at %s ..." "$label" "$url"
	while ! curl -fsS "$url" >/dev/null 2>&1; do
		if (( elapsed >= timeout )); then
			printf "\nTimed out waiting for %s. Check logs.\n" "$label"
			exit 1
		fi
		sleep "$interval"
		elapsed=$((elapsed + interval))
	done
	printf " ready.\n"
}

cleanup() {
	local exit_code=$?
	if [[ -n "${VLLM_PID:-}" ]]; then
		echo "Stopping vLLM server (pid=${VLLM_PID})"
		kill "$VLLM_PID" 2>/dev/null || true
		wait "$VLLM_PID" 2>/dev/null || true
	fi
	if [[ -n "${QWEN_IMAGE_PID:-}" ]]; then
		echo "Stopping Qwen Image Edit server (pid=${QWEN_IMAGE_PID})"
		kill "$QWEN_IMAGE_PID" 2>/dev/null || true
		wait "$QWEN_IMAGE_PID" 2>/dev/null || true
	fi
	exit "$exit_code"
}

trap cleanup EXIT INT TERM

###########################################
# 1) Start the local Qwen Image Edit API. #
###########################################

echo "Starting Qwen Image Edit server on ${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT} (log: ${QWEN_IMAGE_LOG})"
python -m uvicorn llm.qwen-image-edit.server:app \
	--host "$QWEN_IMAGE_HOST" \
	--port "$QWEN_IMAGE_PORT" \
	>"$QWEN_IMAGE_LOG" 2>&1 &
QWEN_IMAGE_PID=$!

wait_for_http "http://${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/health" "Qwen Image Edit" 180

#############################################
# 2) Start vLLM with Qwen/Qwen3-VL-8B model. #
#############################################

echo "Starting vLLM (${VLLM_MODEL}) on ${VLLM_HOST}:${VLLM_PORT} (log: ${VLLM_LOG})"
VLLM_CMD=(vllm serve "$VLLM_MODEL" --host "$VLLM_HOST" --port "$VLLM_PORT")

if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
	# shellcheck disable=SC2206
	VLLM_CMD+=($VLLM_EXTRA_ARGS)
fi

"${VLLM_CMD[@]}" >"$VLLM_LOG" 2>&1 &
VLLM_PID=$!

wait_for_http "http://${VLLM_HOST}:${VLLM_PORT}/v1/models" "vLLM OpenAI server" 240

###########################################
# 3) Export env vars for solve/auto_solve. #
###########################################

export SEE2THINK_LLM_BACKEND=local
export VLLM_BASE_URL="http://${VLLM_HOST}:${VLLM_PORT}/v1"
export VLLM_API_KEY="${LOCAL_VLLM_API_KEY}"

export QWEN_IMAGE_EDIT_BASE_URL="http://${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/v1"
export QWEN_IMAGE_EDIT_API_KEY="${QWEN_IMAGE_EDIT_API_KEY:-EMPTY}"
export QWEN_IMAGE_EDIT_MODEL="${QWEN_IMAGE_EDIT_MODEL:-Qwen-Image-Edit-2509}"

echo "LLM backend -> ${VLLM_BASE_URL} (api_key=${LOCAL_VLLM_API_KEY})"
echo "Qwen Image Edit -> ${QWEN_IMAGE_EDIT_BASE_URL}"

##############################################
# 4) Run a small batch of tasks for the demo.#
##############################################

if [[ ! -f "$TASKS_FILE" ]]; then
	echo "Tasks file not found: $TASKS_FILE" >&2
	exit 1
fi

RUN_CMD=(python solve/run_tasks.py
	"--tasks" "$TASKS_FILE"
	"--mode" "$RUN_MODE"
	"--model" "$RUN_MODEL_NAME"
	"--start" "$TASK_START"
	"--end" "$TASK_END"
	"--workers" "$RUN_WORKERS")

if [[ "$RUN_LINEAR" == "true" ]]; then
	RUN_CMD+=("--linear")
fi
if [[ "$RUN_EXPERIMENT" == "true" ]]; then
	RUN_CMD+=("--experiment")
fi
if [[ -n "$RUN_EXPERIMENT_TYPES" ]]; then
	# shellcheck disable=SC2206
	RUN_CMD+=("--experiment_types" $RUN_EXPERIMENT_TYPES)
fi
if [[ "$RUN_GLOBAL_PARALLEL" == "true" ]]; then
	RUN_CMD+=("--global_parallel")
fi

echo "Running tasks with command:"
printf '  %q' "${RUN_CMD[@]}"
printf '\n'

"${RUN_CMD[@]}"

echo "Experiment completed. Logs:"
echo "  vLLM log:          ${VLLM_LOG}"
echo "  Qwen Image log:    ${QWEN_IMAGE_LOG}"
