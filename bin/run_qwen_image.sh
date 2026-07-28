
#!/usr/bin/env bash
set -euo pipefail

# Usage: HOST=127.0.0.1 PORT=8000 LOG=/tmp/qwen.log ./bin/run_qwen_image.sh

SERVER_PY="llm/qwen-image-edit/server.py"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

SEE2THINK_LOG_DIR="${SEE2THINK_LOG_DIR:-/storage/v-jinpewang/yansiyu_workspace/See2Think/logs}"
LOG="${LOG:-$SEE2THINK_LOG_DIR/qwen_image_server.log}"
# 使用 dirname 提取目录部分 (例如 "logs")
LOG_DIR=$(dirname "$LOG")
# 仅创建目录
if mkdir -p "$LOG_DIR"; then
    echo "日志目录已就绪: $LOG_DIR"
    echo "日志文件路径: $LOG"
else
    echo "错误: 无法创建日志目录 $LOG_DIR" >&2
    exit 1
fi

START_TIMEOUT=${START_TIMEOUT:-600}

if [ ! -f "$SERVER_PY" ]; then
	echo "Server file '$SERVER_PY' not found"
	exit 2
fi

echo "Starting server: python $SERVER_PY (logs -> $LOG)"
nvidia-smi

python -u "$SERVER_PY" >"$LOG" 2>&1 &
SERVER_PID=$!

tail -f "$LOG" & # 在后台启动，把文件内容实时搬运回控制台
TAIL_PID=$!

cleanup() {
	echo "Stopping server (pid=$SERVER_PID)..."
	
	kill "$TAIL_PID" 2>/dev/null || true
	kill "$SERVER_PID" 2>/dev/null || true
	wait "$SERVER_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Waiting up to ${START_TIMEOUT}s for server at http://${HOST}:${PORT}/ to become available..."
elapsed=0
while true; do
	if curl -sSf "http://${HOST}:${PORT}/" >/dev/null 2>&1 || curl -sSf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
		echo "Server is up."
		break
	fi
	sleep 1
	elapsed=$((elapsed + 1))
	if [ "$elapsed" -ge "$START_TIMEOUT" ]; then
		echo "Server did not start within ${START_TIMEOUT}s. See log: $LOG"
		exit 3
	fi
done

echo "Running basic client test..."

python -u llm/qwen-image-edit/client.py

echo "Client tests finished. Script will exit and stop the server." 