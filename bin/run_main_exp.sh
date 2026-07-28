#!/bin/bash

LOG_FILE="logs/main_exp_$(date +'%Y%m%d_%H%M%S').log"

python -m experiment.main_exp \
    --json_path selected_1200.json \
    --model gpt-4o \
    --num_workers 2 \
    --start_idx 10 \
    --num_experiments 2 >> $LOG_FILE 2>&1
