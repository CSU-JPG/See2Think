#!/bin/bash

echo "Starting Multimodal Chain Evaluation..."
echo "Model: ${MODEL_PATH_PREFIX}"
echo "Evaluator: ${EVAL_MODEL}"

# 运行评估脚本
# --max-samples 30，意味着每组只随机抽30题进行精细评估
# 如果跑全量，去掉这个参数或者设大一点
python convert/eval_steps.py \
    --input-files \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_interference_key.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_interference_non_key.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_optional.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_text_only.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_use_depth.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_use_edge.json" \
    --output-file "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_eval_steps_report.json" \
    --max-samples ${MAX_SAMPLES}

echo "Evaluation finished. Report saved to: ${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_eval_steps_report.json"