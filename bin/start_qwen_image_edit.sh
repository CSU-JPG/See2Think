#!/bin/bash

# ================= 配置区域 =================
# 端口 (需要与 model_server.py 中的端口一致)
PORT=${IMG_PORT:-9000}
# 指定 GPU (对应 yaml 中的 4,5,6,7)
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-4,5,6,7}
# 最大等待时间 (秒)
TIMEOUT=600 
# 日志文件
LOG_FILE="${SEE2THINK_LOG_DIR}/qwen_image_edit_server_$(date '+%Y-%m-%d_%H-%M-%S').log"
# ===========================================

if ss -tlnp | grep ":$PORT" > /dev/null; then
    echo "WARNING: Port $PORT is already in use by:"
    ss -tlnp | grep ":$PORT"
    # 可选：自动杀掉占用端口的旧进程（慎用）
    # fuser -k $PORT/tcp
fi

echo ">>> [ImageServer] Starting on GPUs: $CUDA_VISIBLE_DEVICES, Port: $PORT"

echo ">>> [ImageServer] Log file: $LOG_FILE"

# 1. 后台启动服务 (使用 nohup)
nohup python solve/model_server.py > "$LOG_FILE" 2>&1 &

# 获取后台进程的 PID
SERVER_PID=$!
echo ">>> [ImageServer] Process ID: $SERVER_PID"

# 2. 健康检查循环
start_time=$(date +%s)
echo ">>> [ImageServer] Waiting for health check..."

while true; do
    # ---------------------------------------------------------
    # A. 检查进程是否存活 (基本没变，增加显存/内存占用提示可选)
    # ---------------------------------------------------------
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo -e "\n\033[31m!!! [ImageServer] Process $SERVER_PID died unexpectedly!\033[0m"
        echo "--- Last 20 lines of log ---"
        tail -n 20 "$LOG_FILE"
        exit 1
    fi

    # ---------------------------------------------------------
    # B. 检查接口连通性 (核心修改)
    # ---------------------------------------------------------
    # 使用 --max-time 防止 curl 自身卡死
    # 捕获 HTTP 状态码，如果连接拒绝则通常返回 000
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$PORT/health")
    CURL_EXIT_CODE=$?

    # 计算时间
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))

    # ---------------------------------------------------------
    # 状态判断与详细输出
    # ---------------------------------------------------------
    if [ "$HTTP_CODE" == "200" ]; then
        echo -e "\n\033[32m>>> [ImageServer] Service is READY! (HTTP 200) after ${elapsed}s\033[0m"
        break
    elif [ "$HTTP_CODE" == "000" ]; then
        # 000 通常意味着 Connection Refused (服务还没绑定端口)
        printf "\r[Wait: %3ds/%3ds] Status: \033[33mConnecting...\033[0m (Port not ready) " "$elapsed" "$TIMEOUT"
    elif [ "$HTTP_CODE" == "503" ] || [ "$HTTP_CODE" == "500" ]; then
        # 5xx 通常意味着服务起来了，但模型还在加载，或者内部报错
        printf "\r[Wait: %3ds/%3ds] Status: \033[35mLoading...\033[0m    (HTTP %s)    " "$elapsed" "$TIMEOUT" "$HTTP_CODE"
    else
        # 其他奇怪的状态码 (404等)
        printf "\r[Wait: %3ds/%3ds] Status: \033[31mUnexpected\033[0m    (HTTP %s)    " "$elapsed" "$TIMEOUT" "$HTTP_CODE"
    fi

    # ---------------------------------------------------------
    # C. 检查超时
    # ---------------------------------------------------------
    if [ $elapsed -gt $TIMEOUT ]; then
        echo -e "\n\033[31m!!! [ImageServer] Timeout waiting for service start (${TIMEOUT}s).\033[0m"
        echo "--- Last 20 lines of log ---"
        tail -n 20 "$LOG_FILE"
        
        # 尝试打印端口占用情况，帮助排查是否端口冲突
        echo "--- Port $PORT status ---"
        netstat -nlp | grep ":$PORT" || echo "No process on port $PORT"
        
        kill $SERVER_PID
        exit 1
    fi

    sleep 3
done

echo "" # 换行