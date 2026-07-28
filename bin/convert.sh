#!/bin/bash
# convert markdown files to json

# MODEL_PATH_PREFIX="clevr_math/val/banana_qwen3-vl-8b-thinking"
SUFFIXES=("" "_interference_key" "_interference_non_key" "_optional" "_text_only" "_use_depth" "_use_edge")

for i in "${!SUFFIXES[@]}"; do
    # 拼接完整的相对路径
    CURRENT_SUBDIR="${MODEL_PATH_PREFIX}${SUFFIXES[$i]}"
    
    # 自动生成序号
    STEP_NUM=$((i + 1))
    
    echo "Info: ${STEP_NUM}. convert ${CURRENT_SUBDIR}"
    
    python convert/pipeline.py \
        --root-dir "${SEE2THINK_OUTPUT_BASE}/${CURRENT_SUBDIR}" \
        --output-file "${SEE2THINK_OUTPUT_BASE}/${CURRENT_SUBDIR}.json"
done

echo "finish bin/convert.sh"