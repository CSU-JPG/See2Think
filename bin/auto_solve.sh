#!/bin/bash

# python solve/auto_solve.py \
#     --path annotation/dataset/data/clevr_math/val/data.json \
#     --id 0 \
#     --output_dir tasks/banana/clevr_math_val_0 \
#     --mode banana \
#     --model gpt-4o

# python solve/auto_solve.py \
#     --path annotation/dataset/data/clevr_math/val/data.json \
#     --id 1 \
#     --output_dir tasks/banana/clevr_math_val_1 \
#     --mode banana \
#     --model gpt-4o

# python solve/auto_solve.py \
#     --path annotation/dataset/data/m3cot/test0/data.json \
#     --id 4 \
#     --output_dir tasks/banana/m3cot_test0_4 \
#     --mode banana \
#     --model gpt-4o

python solve/auto_solve.py \
    --path annotation/dataset/data/m3cot/test0/data.json \
    --id 2 \
    --output_dir tasks/banana/m3cot_test0_2 \
    --mode banana \
    --model gpt-4o