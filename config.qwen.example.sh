#!/usr/bin/env bash

# Project paths on the rented Linux server.
# Change this to the directory where you unzip/copy this package.
export SEE2THINK_PROJECT_ROOT="/root/autodl-tmp/See2Think"
export SEE2THINK_DATA_BASE="$SEE2THINK_PROJECT_ROOT"
export SEE2THINK_OUTPUT_BASE="$SEE2THINK_PROJECT_ROOT/newtasks"
export SEE2THINK_LOG_DIR="$SEE2THINK_PROJECT_ROOT/newlogs"

# Qwen chat model served by local vLLM.
export SEE2THINK_LLM_BACKEND="vllm"
export VLLM_BASE_URL="http://127.0.0.1:8000/v1"
export VLLM_API_KEY="EMPTY"

# Renderer path used by current VAoT scripts.
# Required by solve/auto_solve.py initialization even for text/no-render.
export GEMINI_API_KEY="PUT_RENDERER_API_KEY_HERE"
export GEMINI_BASE_URL="PUT_RENDERER_BASE_URL_HERE"

# Runtime defaults.
export SEE2THINK_TASK_TIMEOUT_SECONDS="1200"
export PYTHONIOENCODING="utf-8"

# Single-GPU vLLM defaults for rented cards.
# 8B on L40S 48GB and 32B on RTX PRO 6000 96GB should start with TP_SIZE=1.
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export TP_SIZE="${TP_SIZE:-1}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
export MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
