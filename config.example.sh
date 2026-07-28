#!/usr/bin/env bash

# Copy this file to config.sh and fill in your local API settings.
# config.sh is ignored by git and should not be committed.

# Project paths.
export SEE2THINK_PROJECT_ROOT="$(pwd)"
export SEE2THINK_DATA_BASE="$SEE2THINK_PROJECT_ROOT"
export SEE2THINK_OUTPUT_BASE="$SEE2THINK_PROJECT_ROOT/outputs"
export SEE2THINK_LOG_DIR="$SEE2THINK_PROJECT_ROOT/logs"

# Reasoning model backend.
# Use "openai" for OpenAI-compatible hosted APIs, or "vllm" for a local
# OpenAI-compatible vLLM server.
export SEE2THINK_LLM_BACKEND="openai"

# OpenAI-compatible reasoning/judge endpoint.
export OPENAI_API_KEY="PUT_OPENAI_COMPATIBLE_API_KEY_HERE"
export OPENAI_BASE_URL="PUT_OPENAI_COMPATIBLE_BASE_URL_HERE"

# Optional local vLLM endpoint, used only when SEE2THINK_LLM_BACKEND="vllm".
export VLLM_BASE_URL="http://127.0.0.1:8000/v1"
export VLLM_API_KEY="EMPTY"

# Image renderer endpoint used by VAoT-Full and VAoT-WrongRender.
export GEMINI_API_KEY="PUT_RENDERER_API_KEY_HERE"
export GEMINI_BASE_URL="PUT_RENDERER_BASE_URL_HERE"

# Runtime defaults.
export SEE2THINK_TASK_TIMEOUT_SECONDS="1200"
export PYTHONIOENCODING="utf-8"
