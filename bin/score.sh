#!/bin/bash

# python3 eval/score.py \
#     --dataset eval/single_clevr_math_evaluation.json \
#     --output eval/single_clevr_math_evaluation_result.json \
#     --model gpt-4o

# python3 eval/score.py \
#     --dataset eval/m3cot_test0_banana_gpt-4o_evaluation.json \
#     --output eval/m3cot_test0_banana_gpt-4o_evaluation_result.json \
#     --model gpt-4o

# python3 eval/score.py \
#     --dataset eval/clevr_math_val_banana_gpt-4o_evaluation.json \
#     --output eval/clevr_math_val_banana_gpt-4o_evaluation_result.json \
#     --model gpt-4o

python3 eval/score.py \
    --dataset eval/math_code_gpt-4o_evaluation.json \
    --output eval/math_code_gpt-4o_evaluation_result.json \
    --model gpt-4o