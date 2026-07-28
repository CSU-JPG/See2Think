#!/bin/bash

# TASKS_FILE=tasks/m3cot_test0_tasks.json
# MODE=banana
# MODEL=gemini-2.5-pro
# WORKERS=3
# START=0
# END=3

TASKS_FILE=json/tasks_annotation_dataset_data_clevr_math_val_data.json
MODE=banana
MODEL=gpt-4o
WORKERS=3
START=0
END=10

python solve/create_golden.py \
    --tasks "$TASKS_FILE" \
    --mode "$MODE" \
    --model "$MODEL" \
    --workers "$WORKERS" \
    --start "$START" \
    --end "$END"