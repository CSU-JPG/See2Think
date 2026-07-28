#!/bin/bash

python eval/create_config.py \
    --solution-base golden/clevr_math/val/banana_gpt-4o \
    --model-base tasks/out/clevr_math/val/banana_gpt-4o \
    --perturbed-base tasks/out/clevr_math/val/banana_gpt-4o_interference_key \
    --irrelevant-base tasks/out/clevr_math/val/banana_gpt-4o_interference_non_key \
    --output eval/clevr_math_val_banana_gpt-4o_config.json

python eval/generate_evaluation_dataset.py \
    --original annotation/dataset/data/clevr_math/val/data.json \
    --config eval/clevr_math_val_banana_gpt-4o_config.json \
    --output eval/clevr_math_val_banana_gpt-4o_evaluation.json \
    --model gpt-4o

python3 eval/score.py \
    --dataset eval/clevr_math_val_banana_gpt-4o_evaluation.json \
    --output eval/clevr_math_val_banana_gpt-4o_evaluation_result.json \
    --model gpt-4o

python3 eval/summary.py \
    --input eval/clevr_math_val_banana_gpt-4o_evaluation_result.json \
    --output eval/clevr_math_val_banana_gpt-4o_summary.json