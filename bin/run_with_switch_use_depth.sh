#!/bin/bash

#======================================================================#
#                           DEFAULT CONFIG                             #
#======================================================================#

# 默认配置 (如果没有通过命令行传入参数，将使用这些值)
TASKS_FILE="json/tasks_annotation_dataset_data_emma_chemistry_data.json"
MODEL="gpt-5"
MODE="banana"
WORKERS=20
BIAS=0
RUN_LIMIT=20
TASKS_PER_BATCH=20
GOLDEN_MODEL="gpt-4o"

# 默认流程开关
ENABLE_SOLVE=false
ENABLE_GOLDEN=false
ENABLE_EVAL=false

#======================================================================#
#                            ARGUMENT PARSING                          #
#======================================================================#

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -f, --file FILE       任务文件路径 (Default: $TASKS_FILE)"
    echo "  -m, --model MODEL     模型名称 (Default: $MODEL)"
    echo "  -M, --mode MODE       模式 (banana/code) (Default: $MODE)"
    echo "  -b, --bias BIAS       起始偏移量 (Default: $BIAS)"
    echo "  -l, --limit LIMIT     运行任务数量 (Default: $RUN_LIMIT)"
    echo "  -w, --workers NUM     并发工作线程数 (Default: $WORKERS)"
    echo "  --solve               开启 Solve 阶段"
    echo "  --golden              开启 Golden 阶段"
    echo "  --eval                开启 Eval 阶段"
    echo "  --all                 开启所有阶段 (Solve, Golden, Eval)"
    echo "  -h, --help            显示帮助信息"
    exit 1
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--file)
            TASKS_FILE="$2"
            shift 2
            ;;
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -M|--mode)
            MODE="$2"
            shift 2
            ;;
        -b|--bias)
            BIAS="$2"
            shift 2
            ;;
        -l|--limit)
            RUN_LIMIT="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        --solve)
            ENABLE_SOLVE=true
            shift
            ;;
        --golden)
            ENABLE_GOLDEN=true
            shift
            ;;
        --eval)
            ENABLE_EVAL=true
            shift
            ;;
        --all)
            ENABLE_SOLVE=true
            ENABLE_GOLDEN=true
            ENABLE_EVAL=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# 如果没有指定任何阶段，提示用户
if [ "$ENABLE_SOLVE" = false ] && [ "$ENABLE_GOLDEN" = false ] && [ "$ENABLE_EVAL" = false ]; then
    echo "Warning: No stages selected. Use --solve, --golden, --eval, or --all."
fi

#======================================================================#
#                           DATASET MAPPINGS                           #
#======================================================================#

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

#======================================================================#
#                             FUNCTIONS                                #
#======================================================================#

set_eval_paths() {
    local dataset="${EVAL_DATASETS[$1]}"
    local original="${EVAL_ORIGINALS[$1]}"
    local golden_mode="${GOLDEN_MODES[$1]}"
    local start_idx="$2"
    local end_idx="$3"

    [[ -z "$dataset" || -z "$original" || -z "$golden_mode" ]] && { echo "Error: Mapping not defined for $1" >&2; exit 1; }

    local eval_mode_model="${MODE}_${MODEL}"
    local golden_mode_model="${golden_mode}_${GOLDEN_MODEL}"
    
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

#======================================================================#
#                           INITIALIZATION                             #
#======================================================================#

echo "----------------------------------------"
echo "Initializing..."
echo "Using TASKS_FILE: $TASKS_FILE"
echo "Using MODEL: $MODEL"
echo "Using MODE: $MODE"
echo "Using BIAS: $BIAS, LIMIT: $RUN_LIMIT"
echo "Using ENABLE_SOLVE $ENABLE_SOLVE"
echo "Using ENABLE_GOLDEN $ENABLE_GOLDEN"
echo "Using ENABLE_EVAL $ENABLE_EVAL"

# 如果设置了 SEE2THINK_DATA_BASE，则打印该信息
if [ -n "$SEE2THINK_DATA_BASE" ]; then
    echo "Using SEE2THINK_DATA_BASE: $SEE2THINK_DATA_BASE"
fi

sleep 1
START_TIME=$(date +%Y-%m-%d\ %H:%M:%S)

# --- 计算任务范围 ---
REAL_TOTAL_TASKS=$(python -u - <<PY
import json
import sys
try:
    with open("${TASKS_FILE}") as f:
        print(len(json.load(f)))
except FileNotFoundError:
    print(0)
    sys.exit(1)
except Exception:
    print(0)
PY
)

# 检查文件是否存在
if [ $? -ne 0 ]; then
    echo "Error: Task file not found: $TASKS_FILE"
    exit 1
fi

FINAL_END=$(( BIAS + RUN_LIMIT ))

if (( FINAL_END > REAL_TOTAL_TASKS )); then
    FINAL_END=$REAL_TOTAL_TASKS
fi

if (( BIAS >= REAL_TOTAL_TASKS )); then
    echo "Error: BIAS ($BIAS) is >= total tasks ($REAL_TOTAL_TASKS). Exiting."
    exit 1
fi

# --- 日志配置 ---
LOG_DIR="${SEE2THINK_LOG_DIR}"
mkdir -p "$LOG_DIR"
TASK_BASENAME=$(basename "$TASKS_FILE" .json)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/${TASK_BASENAME}_${MODEL}_${BIAS}_to_${FINAL_END}_${TIMESTAMP}.log"

echo "========================================================"
echo " LOGGING STARTED"
echo " Log File: $LOG_FILE"
echo "========================================================"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "Dataset Total: $REAL_TOTAL_TASKS"
echo "Running Range: $BIAS to $FINAL_END (Limit: $RUN_LIMIT)"
echo "Start Time: $START_TIME"

#======================================================================#
#                            STAGES                                    #
#======================================================================#

# --- Stage 1: Run Solver ---
stage_run_solver() {
    echo ""
    echo "########################################################"
    echo "#                 STAGE: RUN TASKS                     #"
    echo "########################################################"

    for ((START=BIAS; START<FINAL_END; START+=TASKS_PER_BATCH)); do
        END=$((START+TASKS_PER_BATCH))
        (( END > FINAL_END )) && END=$FINAL_END
        
        echo "--------------------------------------------------------"
        echo "[$(date +%T)] Solving Batch: $START to $END"
        
        python -u solve/run_tasks.py \
            --tasks "$TASKS_FILE" \
            --mode "$MODE" \
            --model "$MODEL" \
            --workers "$WORKERS" \
            --start "$START" \
            --end "$END" \
            --experiment \
            --experiment_types use_depth \
            --global_parallel
    done
}

# --- Stage 2: Create Golden ---
stage_generate_golden() {
    echo ""
    echo "########################################################"
    echo "#               STAGE: CREATE GOLDEN                   #"
    echo "########################################################"

    local current_golden_mode=${GOLDEN_MODES[$TASKS_FILE]}
    
    if [[ -z "$current_golden_mode" ]]; then
         echo "Error: No golden mode defined for $TASKS_FILE"
         return
    fi

    echo "Golden Model: $GOLDEN_MODEL"
    echo "Golden Mode: $current_golden_mode"

    for ((START=BIAS; START<FINAL_END; START+=TASKS_PER_BATCH)); do
        END=$((START+TASKS_PER_BATCH))
        (( END > FINAL_END )) && END=$FINAL_END

        echo "--------------------------------------------------------"
        echo "[$(date +%T)] Golden Batch: $START to $END"

        python -u solve/create_golden.py \
            --tasks "$TASKS_FILE" \
            --mode "$current_golden_mode" \
            --model "$GOLDEN_MODEL" \
            --workers "$WORKERS" \
            --start "$START" \
            --end "$END"
    done
}

# --- Stage 3: Evaluation ---
stage_evaluate() {
    echo ""
    echo "########################################################"
    echo "#                 STAGE: EVALUATION                    #"
    echo "########################################################"

    set_eval_paths "$TASKS_FILE" "$BIAS" "$FINAL_END"
    
    JUDGE_MODEL="gpt-4o"
    echo "Evaluation Config File: $EVAL_CONFIG"

    backup_if_exists "$EVAL_CONFIG"
    echo "[$(date +%T)] Creating config..."
    python -u eval/create_config.py \
        --solution-base "$SOLUTION_BASE" \
        --model-base "$MODEL_BASE" \
        --perturbed-base "$PERTURBED_BASE" \
        --irrelevant-base "$IRRELEVANT_BASE" \
        --text-only-base "$TEXT_ONLY" \
        --output "$EVAL_CONFIG" \
        --start "$BIAS" \
        --end "$FINAL_END"

    backup_if_exists "$EVAL_DATASET"
    echo "[$(date +%T)] Generating evaluation dataset..."
    python -u eval/generate_evaluation_dataset.py \
        --original "$ORIGINAL_DATASET" \
        --config "$EVAL_CONFIG" \
        --output "$EVAL_DATASET" \
        --model "$MODEL"

    backup_if_exists "$EVAL_RESULT"
    echo "[$(date +%T)] Scoring..."
    python -u eval/score.py \
        --dataset "$EVAL_DATASET" \
        --output "$EVAL_RESULT" \
        --model "$JUDGE_MODEL"

    backup_if_exists "$EVAL_SUMMARY"
    echo "[$(date +%T)] Summarizing..."
    python -u eval/summary.py \
        --input "$EVAL_RESULT" \
        --output "$EVAL_SUMMARY"
}

#======================================================================#
#                            EXECUTION                                 #
#======================================================================#

if [ "$ENABLE_SOLVE" = true ]; then
    stage_run_solver
else
    echo "Skipping Solver Stage..."
fi

if [ "$ENABLE_GOLDEN" = true ]; then
    stage_generate_golden
else
    echo "Skipping Golden Generation Stage..."
fi

if [ "$ENABLE_EVAL" = true ]; then
    stage_evaluate
else
    echo "Skipping Evaluation Stage..."
fi

#======================================================================#
#                               DONE                                   #
#======================================================================#

END_TIME=$(date +%Y-%m-%d\ %H:%M:%S)
echo ""
echo "========================================================"
echo " DONE"
echo " Time elapsed: $START_TIME to $END_TIME"
echo " Log saved to: $LOG_FILE"
echo "========================================================"