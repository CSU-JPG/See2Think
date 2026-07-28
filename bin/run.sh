#!/bin/bash

#==============================#
#            solve             #
#==============================#

# run tasks 

# TASKS_FILE="json/tasks_annotation_dataset_data_prism_text_letter_number_data.json"
# MODEL="gpt-4o"
# MODE="banana"
# WORKERS=3

# TASKS_FILE="json/tasks_annotation_dataset_data_math_data.json"
# MODEL="gpt-4o"
# MODE="code"
# WORKERS=5

TASKS_FILE="json/tasks_annotation_dataset_data_m3cot_test0_data.json"
MODEL="gpt-4o"
MODE="banana"
WORKERS=3

echo "Using TASKS_FILE: $TASKS_FILE"
echo "Using MODEL: $MODEL"
echo "Using MODE: $MODE"

sleep 5

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
    [[ -z "$dataset" || -z "$original" || -z "$golden_mode" ]] && { echo "未定义 $1 的映射" >&2; exit 1; }

    local eval_mode_model="${MODE}_${MODEL}"
    local golden_mode_model="${golden_mode}_${GOLDEN_MODEL}"
    local dataset_key="${dataset//\//_}_${eval_mode_model}"

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
        echo "已备份 $file -> $backup"
    fi
}

TOTAL_TASKS=$(python -u - <<PY
import json
with open("${TASKS_FILE}") as f:
    print(len(json.load(f)))
PY
)
if (( TOTAL_TASKS > 50 )); then
    TOTAL_TASKS=50
fi

echo "starting tasks from $TASKS_FILE with total tasks: $TOTAL_TASKS"

# backup_if_exists "tasks/out"
for ((START=0; START<TOTAL_TASKS; START+=TASKS_PER_BATCH)); do
    END=$((START+TASKS_PER_BATCH))
    (( END > TOTAL_TASKS )) && END=$TOTAL_TASKS
    echo "Processing tasks from $START to $END"

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

echo "completed all tasks($TOTAL_TASKS) from $TASKS_FILE"

#==============================#
#          evaluation          #
#==============================#

set_eval_paths "$TASKS_FILE"

JUDGE_MODEL="gpt-4o"

backup_if_exists "$EVAL_CONFIG"
python -u eval/create_config.py \
    --solution-base $SOLUTION_BASE \
    --model-base $MODEL_BASE \
    --perturbed-base $PERTURBED_BASE \
    --irrelevant-base $IRRELEVANT_BASE \
    --text-only-base $TEXT_ONLY \
    --output $EVAL_CONFIG

backup_if_exists "$EVAL_DATASET"
echo "running cmd: python -u eval/generate_evaluation_dataset.py --original $ORIGINAL_DATASET --config $EVAL_CONFIG --output $EVAL_DATASET --model $MODEL"
python -u eval/generate_evaluation_dataset.py \
    --original $ORIGINAL_DATASET \
    --config $EVAL_CONFIG \
    --output $EVAL_DATASET \
    --model $MODEL

backup_if_exists "$EVAL_RESULT"
echo "running cmd: python -u eval/score.py --dataset $EVAL_DATASET --output $EVAL_RESULT --model $JUDGE_MODEL"
python -u eval/score.py \
    --dataset $EVAL_DATASET \
    --output $EVAL_RESULT \
    --model $JUDGE_MODEL

backup_if_exists "$EVAL_SUMMARY"
echo "running cmd: python -u eval/summary.py --input $EVAL_RESULT --output $EVAL_SUMMARY"
python -u eval/summary.py \
    --input $EVAL_RESULT \
    --output $EVAL_SUMMARY

END_TIME=$(date +%Y-%m-%d\ %H:%M:%S)
echo "time elapsed from $START_TIME to $END_TIME"