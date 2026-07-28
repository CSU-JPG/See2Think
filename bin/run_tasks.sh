#!/bin/bash

# python solve/run_tasks.py \
#     --tasks tasks/clevr_math_val_tasks.json \
#     --mode banana \
#     --model gpt-4o \
#     --workers 5 \
#     --start 0 \
#     --end 5 \
#     --experiment

# python solve/run_tasks.py \
#     --tasks tasks/math_tasks.json \
#     --mode code \
#     --model gpt-4o-mini \
#     --start 0 \
#     --end 5 \
#     --workers 5 \
#     --experiment

# python solve/run_tasks.py \
#     --tasks tasks/m3cot_test1_tasks.json \
#     --mode banana \
#     --model gpt-4o-mini \
#     --start 0 \
#     --end 5 \
#     --workers 5 \
#     --experiment

# python solve/run_tasks.py \
#     --tasks tasks/m3cot_test0_tasks.json \
#     --mode banana \
#     --model gpt-4o \
#     --start 0 \
#     --end 3 \
#     --workers 3 \
#     --experiment

# python solve/run_tasks.py \
#     --tasks tasks/clevr_math_val_tasks.json \
#     --mode banana \
#     --model gpt-4o \
#     --start 0 \
#     --end 3 \
#     --workers 3 \
#     --experiment

python solve/run_tasks.py \
    --tasks json/tasks_annotation_dataset_data_clevr_math_val_data.json \
    --mode banana \
    --model gpt-4o \
    --start 0 \
    --end 10 \
    --linear \
    --experiment \
    --experiment_types interference_non_key interference_key