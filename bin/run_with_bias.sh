#!/bin/bash

#==============================#
#             solve            #
#==============================#

# Config
TASKS_FILE="json/tasks_annotation_dataset_data_m3cot_test0_data.json"
MODEL="gpt-4o"
MODE="banana"
WORKERS=3

# --- 偏移量与任务数量控制 ---
BIAS=0           # 起始索引 (Start Index)
RUN_LIMIT=50     # 本次脚本运行处理的最大任务数 (Limit)

echo "----------------------------------------"
echo "Initializing..."
echo "Using TASKS_FILE: $TASKS_FILE"
echo "Using MODEL: $MODEL"
echo "Using MODE: $MODE"
echo "Using BIAS: $BIAS, LIMIT: $RUN_LIMIT"

sleep 2

START_TIME=$(date +%Y-%m-%d\ %H:%M:%S)

TASKS_PER_BATCH=10
GOLDEN_MODEL="gpt-4o"

declare -A GOLDEN_MODES=(
    ["json/tasks_annotation_dataset_data_clevr_math_val_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_emma_chemistry_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_emma_math_data.json"]="code"
    ["json/tasks_annotation_dataset_data_emma_physics_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_m3cot_test0_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_m3cot_test1_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_math_data.json"]="code"
    ["json/tasks_annotation_dataset_data_prism_black_white_blocks_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_prism_position_style_attribute_count_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_prism_shape_reasoning_others_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_prism_spatial_reasoning_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_prism_special_patterns_data.json"]="banana"
    ["json/tasks_annotation_dataset_data_prism_text_letter_number_data.json"]="banana"
)

declare -A EVAL_DATASETS=(
    ["json/tasks_annotation_dataset_data_clevr_math_val_data.json"]="clevr_math/val"
    ["json/tasks_annotation_dataset_data_emma_chemistry_data.json"]="emma/chemistry"
    ["json/tasks_annotation_dataset_data_emma_math_data.json"]="emma/math"
    ["json/tasks_annotation_dataset_data_emma_physics_data.json"]="emma/physics"
    ["json/tasks_annotation_dataset_data_m3cot_test0_data.json"]="m3cot/test0"
    ["json/tasks_annotation_dataset_data_m3cot_test1_data.json"]="m3cot/test1"
    ["json/tasks_annotation_dataset_data_math_data.json"]="math"
    ["json/tasks_annotation_dataset_data_prism_black_white_blocks_data.json"]="prism/black_white_blocks"
    ["json/tasks_annotation_dataset_data_prism_position_style_attribute_count_data.json"]="prism/position_style_attribute_count"
    ["json/tasks_annotation_dataset_data_prism_shape_reasoning_others_data.json"]="prism/shape_reasoning_others"
    ["json/tasks_annotation_dataset_data_prism_spatial_reasoning_data.json"]="prism/spatial_reasoning"
    ["json/tasks_annotation_dataset_data_prism_special_patterns_data.json"]="prism/special_patterns"
    ["json/tasks_annotation_dataset_data_prism_text_letter_number_data.json"]="prism/text_letter_number"
)
declare -A EVAL_ORIGINALS=(
    ["json/tasks_annotation_dataset_data_clevr_math_val_data.json"]="annotation/dataset/data/clevr_math/val/data.json"
    ["json/tasks_annotation_dataset_data_emma_chemistry_data.json"]="annotation/dataset/data/emma/chemistry/data.json"
    ["json/tasks_annotation_dataset_data_emma_math_data.json"]="annotation/dataset/data/emma/math/data.json"
    ["json/tasks_annotation_dataset_data_emma_physics_data.json"]="annotation/dataset/data/emma/physics/data.json"
    ["json/tasks_annotation_dataset_data_m3cot_test0_data.json"]="annotation/dataset/data/m3cot/test0/data.json"
    ["json/tasks_annotation_dataset_data_m3cot_test1_data.json"]="annotation/dataset/data/m3cot/test1/data.json"
    ["json/tasks_annotation_dataset_data_math_data.json"]="annotation/dataset/data/math/data.json"
    ["json/tasks_annotation_dataset_data_prism_black_white_blocks_data.json"]="annotation/dataset/data/prism/black_white_blocks/data.json"
    ["json/tasks_annotation_dataset_data_prism_position_style_attribute_count_data.json"]="annotation/dataset/data/prism/position_style_attribute_count/data.json"
    ["json/tasks_annotation_dataset_data_prism_shape_reasoning_others_data.json"]="annotation/dataset/data/prism/shape_reasoning_others/data.json"
    ["json/tasks_annotation_dataset_data_prism_spatial_reasoning_data.json"]="annotation/dataset/data/prism/spatial_reasoning/data.json"
    ["json/tasks_annotation_dataset_data_prism_special_patterns_data.json"]="annotation/dataset/data/prism/special_patterns/data.json"
    ["json/tasks_annotation_dataset_data_prism_text_letter_number_data.json"]="annotation/dataset/data/prism/text_letter_number/data.json"
)

set_eval_paths() {
    local dataset="${EVAL_DATASETS[$1]}"
    local original="${EVAL_ORIGINALS[$1]}"
    local golden_mode="${GOLDEN_MODES[$1]}"
    local start_idx="$2"
    local end_idx="$3"

    [[ -z "$dataset" || -z "$original" || -z "$golden_mode" ]] && { echo "Error: Mapping not defined for $1" >&2; exit 1; }

    local eval_mode_model="${MODE}_${MODEL}"
    local golden_mode_model="${golden_mode}_${GOLDEN_MODEL}"
    
    # 文件名包含 start_end 以区分
    local dataset_key="${dataset//\//_}_${eval_mode_model}_${start_idx}_${end_idx}"

    SOLUTION_BASE="golden/${dataset}/${golden_mode_model}"
    MODEL_BASE="tasks/out/${dataset}/${eval_mode_model}"
    PERTURBED_BASE="tasks/out/${dataset}/${eval_mode_model}_interference_key"
    IRRELEVANT_BASE="tasks/out/${dataset}/${eval_mode_model}_interference_non_key"
    TEXT_ONLY="tasks/out/${dataset}/${eval_mode_model}_text_only"

    EVAL_CONFIG="eval/${dataset_key}_config.json"
    EVAL_DATASET="eval/${dataset_key}_evaluation.json"
    EVAL_RESULT="eval/${dataset_key}_evaluation_result.json"
    EVAL_SUMMARY="eval/${dataset_key}_summary.json"
    ORIGINAL_DATASET="$original"
    GOLDEN_MODE_SELECTED="$golden_mode"
}

backup_if_exists() {
    local file="$1"
    if [[ -e "$file" ]]; then
        local ts
        ts=$(date +%Y%m%d_%H%M%S)
        local backup="${file}.${ts}.bak"
        mv "$file" "$backup"
        echo "Backup created: $file -> $backup"
    fi
}

# --- 计算任务范围 ---
REAL_TOTAL_TASKS=$(python -u - <<PY
import json
try:
    with open("${TASKS_FILE}") as f:
        print(len(json.load(f)))
except Exception:
    print(0)
PY
)

FINAL_END=$(( BIAS + RUN_LIMIT ))

if (( FINAL_END > REAL_TOTAL_TASKS )); then
    FINAL_END=$REAL_TOTAL_TASKS
fi

if (( BIAS >= REAL_TOTAL_TASKS )); then
    echo "Error: BIAS ($BIAS) is >= total tasks ($REAL_TOTAL_TASKS). Exiting."
    exit 1
fi

# ======================================================
# [新增] 日志系统配置
# ======================================================
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

# 提取文件名 (无路径和扩展名) 用于日志命名
TASK_BASENAME=$(basename "$TASKS_FILE" .json)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 日志文件名包含：任务名、起始索引、结束索引、时间戳
LOG_FILE="${LOG_DIR}/${TASK_BASENAME}_${BIAS}_to_${FINAL_END}_${TIMESTAMP}.log"

echo "========================================================"
echo " LOGGING STARTED"
echo " Log File: $LOG_FILE"
echo "========================================================"

# 核心魔法：将当前 shell 之后的所有 stdout(1) 和 stderr(2) 
# 都重定向到 tee，tee 会同时输出到屏幕和 LOG_FILE
exec > >(tee -a "$LOG_FILE") 2>&1

# ------------------------------------------------------

echo "Dataset Total: $REAL_TOTAL_TASKS"
echo "Running Range: $BIAS to $FINAL_END (Limit: $RUN_LIMIT)"
echo "Start Time: $START_TIME"

# backup_if_exists "tasks/out"

# --- 处理循环 ---
for ((START=BIAS; START<FINAL_END; START+=TASKS_PER_BATCH)); do
    END=$((START+TASKS_PER_BATCH))
    (( END > FINAL_END )) && END=$FINAL_END
    
    echo "--------------------------------------------------------"
    echo "[$(date +%T)] Processing Batch: $START to $END"
    echo "--------------------------------------------------------"

    python -u solve/run_tasks.py \
        --tasks $TASKS_FILE \
        --mode $MODE \
        --model $MODEL \
        --workers $WORKERS \
        --start $START \
        --end $END \
        --experiment

    python -u solve/create_golden.py \
        --tasks $TASKS_FILE \
        --mode ${GOLDEN_MODE_SELECTED:-${GOLDEN_MODES[$TASKS_FILE]}} \
        --model $GOLDEN_MODEL \
        --workers $WORKERS \
        --start $START \
        --end $END
done

echo "--------------------------------------------------------"
echo "Completed tasks chunk from $BIAS to $FINAL_END"
echo "--------------------------------------------------------"

#==============================#
#           evaluation         #
#==============================#

set_eval_paths "$TASKS_FILE" "$BIAS" "$FINAL_END"

JUDGE_MODEL="gpt-4o"

echo "Evaluation Config File: $EVAL_CONFIG"

backup_if_exists "$EVAL_CONFIG"
echo "[$(date +%T)] Creating config..."
python -u eval/create_config.py \
    --solution-base $SOLUTION_BASE \
    --model-base $MODEL_BASE \
    --perturbed-base $PERTURBED_BASE \
    --irrelevant-base $IRRELEVANT_BASE \
    --text-only-base $TEXT_ONLY \
    --output $EVAL_CONFIG

backup_if_exists "$EVAL_DATASET"
echo "[$(date +%T)] Generating evaluation dataset..."
python -u eval/generate_evaluation_dataset.py \
    --original $ORIGINAL_DATASET \
    --config $EVAL_CONFIG \
    --output $EVAL_DATASET \
    --model $MODEL

backup_if_exists "$EVAL_RESULT"
echo "[$(date +%T)] Scoring..."
python -u eval/score.py \
    --dataset $EVAL_DATASET \
    --output $EVAL_RESULT \
    --model $JUDGE_MODEL

backup_if_exists "$EVAL_SUMMARY"
echo "[$(date +%T)] Summarizing..."
python -u eval/summary.py \
    --input $EVAL_RESULT \
    --output $EVAL_SUMMARY

END_TIME=$(date +%Y-%m-%d\ %H:%M:%S)
echo "========================================================"
echo " DONE"
echo " Time elapsed: $START_TIME to $END_TIME"
echo " Log saved to: $LOG_FILE"
echo "========================================================"