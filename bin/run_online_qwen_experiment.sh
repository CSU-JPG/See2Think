#!/usr/bin/env bash

# 使用在线 API 版本的大模型与本地启动的 Qwen Image Edit 服务进行端到端实验。
# 该脚本只负责启动图像编辑服务，LLM 通过远程 HTTP 接口访问。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

#############################
# 可配置的实验环境参数。     #
#############################

# 在线 LLM (OpenAI 兼容接口) 相关
RUN_MODE="${RUN_MODE:-qwen}"               # solve/run_tasks.py 的 --mode
RUN_MODEL_NAME="${RUN_MODEL_NAME:-gpt-4o}" # solve/run_tasks.py 的 --model
RUN_WORKERS="${RUN_WORKERS:-1}"
RUN_LINEAR="${RUN_LINEAR:-true}"
RUN_EXPERIMENT="${RUN_EXPERIMENT:-false}"
RUN_EXPERIMENT_TYPES="${RUN_EXPERIMENT_TYPES:-}"
RUN_GLOBAL_PARALLEL="${RUN_GLOBAL_PARALLEL:-false}"

# 任务配置
TASKS_FILE="${TASKS_FILE:-json/tasks_annotation_dataset_data_emma_math_data.json}"
TASK_START="${TASK_START:-0}"
TASK_END="${TASK_END:-2}"

# Qwen Image Edit 服务设置（默认模型强制为 qwen-image-edit-2509）
QWEN_IMAGE_HOST="${QWEN_IMAGE_HOST:-127.0.0.1}"
QWEN_IMAGE_PORT="${QWEN_IMAGE_PORT:-8210}"
QWEN_IMAGE_LOG="${QWEN_IMAGE_LOG:-${LOG_DIR}/qwen_image_edit_${TIMESTAMP}.log}"
QWEN_IMAGE_EDIT_MODEL="${QWEN_IMAGE_EDIT_MODEL:-Qwen-Image-Edit-2509}"

#########################
# 基本的合法性检查。    #
#########################

require_env() {
	local name="$1"
	if [[ -z "${!name:-}" ]]; then
		echo "环境变量 ${name} 未设置，请参考 config.sh 配置。" >&2
		exit 1
	fi
}

require_file() {
	local file="$1"
	if [[ ! -f "$file" ]]; then
		echo "找不到任务文件：$file" >&2
		exit 1
	fi
}

require_env OPENAI_API_KEY
require_env OPENAI_BASE_URL
require_env GEMINI_API_KEY
require_env GEMINI_BASE_URL
require_env SEE2THINK_LOCAL_MODELS_BASE

require_file "$TASKS_FILE"

require_bin() {
	if ! command -v "$1" >/dev/null 2>&1; then
		echo "缺少必要命令：$1" >&2
		exit 1
	fi
}

require_bin python
require_bin curl

wait_for_http() {
	local url="$1"
	local label="$2"
	local timeout="${3:-180}"
	local interval=2
	local elapsed=0
	printf "等待 %s (%s) 启动..." "$label" "$url"
	while ! curl -fsS "$url" >/dev/null 2>&1; do
		if (( elapsed >= timeout )); then
			printf "\n等待 %s 超时。\n" "$label"
			exit 1
		fi
		sleep "$interval"
		elapsed=$((elapsed + interval))
	done
	printf " 就绪。\n"
}

cleanup() {
	local exit_code=$?
	if [[ -n "${QWEN_IMAGE_PID:-}" ]]; then
		echo "停止 Qwen Image Edit 服务 (pid=${QWEN_IMAGE_PID})"
		kill "$QWEN_IMAGE_PID" 2>/dev/null || true
		wait "$QWEN_IMAGE_PID" 2>/dev/null || true
	fi
	exit "$exit_code"
}

trap cleanup EXIT INT TERM

#############################################
# 启动本地 Qwen Image Edit API 服务。       #
#############################################

echo "启动 Qwen Image Edit 服务 ${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT} (log: ${QWEN_IMAGE_LOG})"
python -m uvicorn llm.qwen-image-edit.server:app \
	--host "$QWEN_IMAGE_HOST" \
	--port "$QWEN_IMAGE_PORT" \
	>"$QWEN_IMAGE_LOG" 2>&1 &
QWEN_IMAGE_PID=$!

wait_for_http "http://${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/health" "Qwen Image Edit" 300

#########################
# 导出 solve 依赖的环境 #
#########################

# 指定在线大模型
export SEE2THINK_LLM_BACKEND="openai"
export OPENAI_API_KEY
export OPENAI_BASE_URL

# 指定图像编辑模型
export QWEN_IMAGE_EDIT_BASE_URL="${QWEN_IMAGE_EDIT_BASE_URL:-http://${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/v1}"
export QWEN_IMAGE_EDIT_API_KEY="${QWEN_IMAGE_EDIT_API_KEY:-EMPTY}"
export QWEN_IMAGE_EDIT_MODEL

echo "LLM backend -> ${OPENAI_BASE_URL} (api_key=OPENAI_API_KEY)"
echo "Qwen Image Edit -> ${QWEN_IMAGE_EDIT_BASE_URL} (model=${QWEN_IMAGE_EDIT_MODEL})"

##################################
# 构建 solve/run_tasks.py 命令。 #
##################################

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

echo "运行命令："
printf '  %q' "${RUN_CMD[@]}"
printf '\n'

#############################
# 实际执行 solve 任务。     #
#############################

"${RUN_CMD[@]}"

echo "在线 API 实验完成，日志位于：${LOG_DIR}"
