#!/bin/bash

#clevr_math
python solve/create_tasks.py \
    --dataset clevr_math/val \
    --indices "tasks/check_question/clevr_math/indices/*.idx" \
    --save_path tasks/clevr_math_val_tasks.json

#math
python solve/create_tasks.py \
    --dataset math \
    --indices "tasks/check_question/math/indices/*.idx" \
    --save_path tasks/math_tasks.json

#m3cot/test1 -> science
python solve/create_tasks.py \
    --dataset m3cot/test1 \
    --indices "tasks/check_question/science/indices/*.idx" \
    --save_path tasks/m3cot_test1_tasks.json

#m3cot/test0 -> commonsense
python solve/create_tasks.py \
    --dataset m3cot/test0 \
    --indices "tasks/check_question/commonsense/indices/*.idx" \
    --save_path tasks/m3cot_test0_tasks.json