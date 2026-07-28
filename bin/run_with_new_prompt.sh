#!/bin/bash

export SEE2THINK_OUTPUT_BASE='new-prompt/out'

python -u solve/run_tasks.py \
    --tasks json/tasks_annotation_dataset_data_clevr_math_val_data.json \
    --mode banana \
    --model o3 \
    --workers 10 \
    --start 0 \
    --end 10