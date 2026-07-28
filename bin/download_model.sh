#!/bin/bash

# ================= 1. 变量检查 =================
# 检查环境变量是否已设置
# -z 判断字符串是否为空
if [ -z "$MODEL_ID" ]; then
    echo "❌ 错误: 未设置环境变量 MODEL_ID"
    echo "用法示例: MODEL_ID='OpenGVLab/InternVL3-2B' FINAL_DEST='/storage/v-jinpewang/yansiyu_workspace/See2Think/models/InternVL3-2B' bash $0"
    exit 1
fi

if [ -z "$FINAL_DEST" ]; then
    echo "❌ 错误: 未设置环境变量 FINAL_DEST"
    exit 1
fi

# 定义计算节点的本地临时下载路径 (保持不变)
LOCAL_TEMP="/tmp/model_download_workspace"

# ================= 2. 环境准备 =================
echo "[INFO] === 步骤 1/3: 环境配置 ==="
echo "[INFO] 模型 ID (来自环境变量): $MODEL_ID"
echo "[INFO] 目标路径 (来自环境变量): $FINAL_DEST"

export HF_HOME="/tmp/hf_cache"
unset HF_HUB_ENABLE_HF_TRANSFER 

mkdir -p "$LOCAL_TEMP"
mkdir -p "$FINAL_DEST"

# ================= 3. 下载到本地 SSD =================
echo "[INFO] === 步骤 2/3: 开始下载到本地 SSD ($LOCAL_TEMP) ==="

# 这里 Python 代码中的 $MODEL_ID 会被 Bash 替换为环境变量的值
python3 -c "
import os
from huggingface_hub import snapshot_download

try:
    print('正在下载: $MODEL_ID ...')
    snapshot_download(
        repo_id='$MODEL_ID',
        local_dir='$LOCAL_TEMP',
        local_dir_use_symlinks=False,
        resume_download=True,
        max_workers=4
    )
    print('[SUCCESS] 本地下载完成！')
except Exception as e:
    print(f'[ERROR] 下载失败: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "[ERROR] 下载步骤失败，脚本退出。"
    exit 1
fi

# ================= 4. 搬运到网络盘 =================
echo "[INFO] === 步骤 3/3: 正在将模型搬运到: $FINAL_DEST ==="

cp -r "$LOCAL_TEMP/"* "$FINAL_DEST/"

if [ $? -eq 0 ]; then
    echo "[SUCCESS] 全部完成！"
    rm -rf "$LOCAL_TEMP"
    rm -rf "/tmp/hf_cache"
else
    echo "[ERROR] 搬运文件失败！"
    exit 1
fi