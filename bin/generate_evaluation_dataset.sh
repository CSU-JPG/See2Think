#!/bin/bash

# python generate_evaluation_dataset.py \
#     --original annotation/dataset/data/math/data.json \
#     --solutions golden/golden-2/math \
#     --models tasks/archieve-10-20/math/code_gpt-5_irrelevant_image \
#     --output math_evaluation_dataset.json

# python generate_evaluation_dataset.py \
#     --original annotation/dataset/data/math/data.json \
#     --solution-file golden/golden-3/math/code_gemini-2.5-pro/3/steps.md \
#     --model-file tasks/archieve-10-20/math/code_gpt-5_irrelevant_image/3/steps.md \
#     --question-id 3 \
#     --output single_evaluation.json

# python eval/generate_evaluation_dataset.py \
#     --original annotation/dataset/data/clevr_math/val/data.json \
#     --config config.json \
#     --output eval/clevr_math_batch_evaluation.json \
#     --model banana_gemini-2.5-pro

# python eval/generate_evaluation_dataset.py \
#     --original annotation/dataset/data/m3cot/test0/data.json \
#     --config eval/m3cot_test0_banana_gpt-4o_config.json \
#     --output eval/m3cot_test0_banana_gpt-4o_evaluation.json \
#     --model banana_gpt-4o

# python eval/generate_evaluation_dataset.py \
#     --original annotation/dataset/data/clevr_math/val/data.json \
#     --config eval/clevr_math_val_banana_gpt-4o_config.json \
#     --output eval/clevr_math_val_banana_gpt-4o_evaluation.json \
#     --model banana_gpt-4o

python eval/generate_evaluation_dataset.py \
    --original annotation/dataset/data/math/data.json \
    --config eval/math_code_gpt-4o_config.json \
    --output eval/math_code_gpt-4o_evaluation.json \
    --model code_gpt-4o