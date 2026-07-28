#!/bin/bash

# ================= 1. 动态配置加载 =================
# 核心逻辑：${VAR:-DEFAULT} -> 有环境变量则用环境变量，否则用默认值

# 模型路径
DEFAULT_MODEL_PATH="/storage/v-jinpewang/yansiyu_workspace/models/Qwen3-VL-8B-Thinking"
MODEL_PATH=${MODEL_PATH:-$DEFAULT_MODEL_PATH}

# 服务名称：auto_solve.py 的 -M 参数需要匹配这个名字
SERVED_NAME=${SERVED_MODEL_NAME:-"qwen3-vl-8b-thinking"}

# 显卡设置：默认使用 0,1,2,3,4,5,6,7 号卡
GPU_IDS=${CUDA_VISIBLE_DEVICES:-"0,1,2,3,4,5,6,7"}

# 服务端口
PORT=${VLLM_PORT:-8000}

# 计算 Tensor Parallel Size (TP)
# 逻辑：自动计算 GPU_IDS 里有几个 ID。如果环境变量手动设置了 TP_SIZE，则优先使用。
if [ -z "$TP_SIZE" ]; then
    # 简单的逻辑：通过逗号分割计算 GPU 数量
    TP_SIZE=$(echo $GPU_IDS | tr ',' '\n' | wc -l)
else
    TP_SIZE=$TP_SIZE
fi

# 显存占用率
# 如果经常遇到 OOM，可以尝试调低
GPU_MEM_UTIL=${GPU_MEMORY_UTILIZATION:-0.6}

# 上下文长度
MAX_LEN=${MAX_MODEL_LEN:-65536}

# 最大并发序列数。大模型显存紧张时设为 1，可以降低 warmup 和运行时显存压力。
MAX_NUM_SEQS_ARG=""
if [ -n "$MAX_NUM_SEQS" ]; then
    MAX_NUM_SEQS_ARG="--max-num-seqs $MAX_NUM_SEQS"
fi
# =================================================

# 导出显卡变量
export CUDA_VISIBLE_DEVICES=$GPU_IDS

# ================= 2. 打印启动信息 =================
echo "----------------------------------------"
echo "启动 vLLM 模型服务"
echo "----------------------------------------"
echo "模型路径: $MODEL_PATH"
echo "服务别名: $SERVED_NAME"
echo "使用显卡: $GPU_IDS (TP=$TP_SIZE)"
echo "监听端口: $PORT"
echo "显存利用: $GPU_MEM_UTIL"
echo "上下文长度: $MAX_LEN"
if [ -n "$MAX_NUM_SEQS" ]; then
    echo "最大并发序列数: $MAX_NUM_SEQS"
fi
echo "----------------------------------------"

# ================= 3. 启动服务 =================

# 创建server日志
DEFAULT_LOGS_BASE="/storage/v-jinpewang/yansiyu_workspace/See2Think/logs"
LOG_BASE=${SEE2THINK_LOG_DIR:-$DEFAULT_LOGS_BASE}
SERVER_LOG=$LOG_BASE/vllm_${SERVED_NAME}_server_$(date '+%Y-%m-%d_%H-%M-%S').log

echo "日志路径: $SERVER_LOG"

nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$SERVED_NAME" \
    --trust-remote-code \
    --port "$PORT" \
    --tensor-parallel-size "$TP_SIZE" \
    --gpu-memory-utilization "$GPU_MEM_UTIL" \
    --max-model-len "$MAX_LEN" \
    $MAX_NUM_SEQS_ARG \
    --host 0.0.0.0 \
    > $SERVER_LOG 2>&1 &

VLLM_PID=$!

# echo "vLLM启动中 (PID=$VLLM_PID) , 等待模型加载完成..."

# for i in {1..300}; do
#     if curl -s http://localhost:$PORT/v1/models -H "Authorization: Bearer $VLLM_API_KEY" | grep '"id"'; then
#         echo "vLLM 服务已就绪：模型加载完成！"
#         exit 0
#     fi
#     if [ $((i % 20)) -eq 0 ]; then
#         echo "已等待 $((i*5)) 秒...（查看 vllm_server.log 确认无 OOM）"
#         tail -n 5 vllm_server.log
#     fi
#     sleep 5
# done

# echo "超时：vLLM 未在 25 分钟内加载模型！"
# echo ">>> 最后 50 行日志："
# tail -n 50 vllm_server.log
# kill $VLLM_PID 2>/dev/null
# exit 1

MAX_WAIT=1800  # 30分钟最大等待时间
CHECK_INTERVAL=5
WAIT_COUNT=0

echo "开始健康检查..."

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    # 检查1: 进程是否存活
    if ! ps -p $VLLM_PID > /dev/null 2>&1; then
        echo "错误: vLLM进程已退出!"
        echo ">>> 最后50行日志:"
        tail -n 50 $SERVER_LOG
        exit 1
    fi
    
    # 检查2: 端口是否监听
    if ! ss -tlnp | grep -q ":$PORT "; then
        echo "端口 $PORT 尚未监听..."
        WAIT_COUNT=$((WAIT_COUNT + CHECK_INTERVAL))
        sleep $CHECK_INTERVAL
        continue
    fi
    
    # 检查3: /v1/models端点是否返回正确格式
    MODEL_RESPONSE=$(curl -s -f --max-time 10 "http://localhost:$PORT/v1/models" -H "Authorization: Bearer $VLLM_API_KEY" 2>/dev/null || echo "FAILED")
    
    if [ "$MODEL_RESPONSE" = "FAILED" ]; then
        echo "端点 /v1/models 无响应..."
    elif echo "$MODEL_RESPONSE" | grep -q '"id"' && echo "$MODEL_RESPONSE" | grep -q '"object"' && echo "$MODEL_RESPONSE" | grep -q "$SERVED_NAME"; then
        # 检查4: /health端点 (如果支持)
        HEALTH_RESPONSE=$(curl -s -f --max-time 10 "http://localhost:$PORT/health" -H "Authorization: Bearer $VLLM_API_KEY"  2>/dev/null || echo "FAILED")
        
        # 检查5: 尝试一个简单的生成请求
        echo "测试生成请求..."
        TEST_RESPONSE=$(curl -s -f --max-time 30 "http://localhost:$PORT/v1/completions" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $VLLM_API_KEY" \
            -d '{
                "model": "'"$SERVED_NAME"'",
                "prompt": "Hello",
                "max_tokens": 5
            }' 2>/dev/null || echo "FAILED")
        
        if echo "$TEST_RESPONSE" | grep -q '"object"' || echo "$TEST_RESPONSE" | grep -q '"choices"'; then
            echo "========================================"
            echo "vLLM 服务完全就绪！"
            echo "模型名称: $SERVED_NAME"
            echo "监听地址: http://localhost:$PORT"
            echo "测试请求: 成功"
            echo "启动时间: $((WAIT_COUNT)) 秒"
            echo "========================================"
            
            # 打印最终状态
            echo "当前进程状态:"
            ps -p $VLLM_PID -o pid,cmd,etime
            
            echo "端口监听状态:"
            ss -tlnp | grep ":$PORT"
            
            echo "GPU 使用情况:"
            nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv -i $GPU_IDS
            
            exit 0
        else
            echo "测试生成请求失败，继续等待..."
        fi
    fi
    
    # 定期打印日志和状态
    if [ $((WAIT_COUNT % 60)) -eq 0 ]; then
        echo "已等待 $WAIT_COUNT 秒..."
        echo ">>> 最新日志:"
        tail -n 10 $SERVER_LOG | grep -E "(INFO|WARNING|ERROR|ready|Ready|READY)"
        echo ">>> GPU 状态:"
        nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv -i $GPU_IDS 2>/dev/null || echo "无法获取GPU状态"
    fi
    
    WAIT_COUNT=$((WAIT_COUNT + CHECK_INTERVAL))
    sleep $CHECK_INTERVAL
done

echo "超时：vLLM 未在 $((MAX_WAIT / 60)) 分钟内完全启动！"
echo ">>> 最后 100 行日志:"
tail -n 100 vllm_server.log
echo ">>> 错误统计:"
grep -c "ERROR\|error\|Error" vllm_server.log
echo ">>> 内存状态:"
free -h
echo ">>> 显卡状态:"
nvidia-smi
kill $VLLM_PID 2>/dev/null
exit 1
