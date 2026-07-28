#! /bin/bash

# python eval/create_config.py \
#     --solution-base golden/clevr_math/val/banana_gpt-4o \
#     --model-base tasks/out/clevr_math/val/banana_gemini-2.5-pro \
#     --perturbed-base tasks/out/clevr_math/val/banana_gemini-2.5-pro_interference_key \
#     --irrelevant-base tasks/out/clevr_math/val/banana_gemini-2.5-pro_interference_non_key \
#     --text-only-base tasks/out/clevr_math/val/banana_gemini-2.5-pro_text_only \
#     --output config.json

# python eval/create_config.py \
#     --solution-base golden/m3cot/test0/banana_gemini-2.5-pro \
#     --model-base tasks/out/m3cot/test0/banana_gpt-4o \
#     --perturbed-base tasks/out/m3cot/test0/banana_gpt-4o_interference_key \
#     --irrelevant-base tasks/out/m3cot/test0/banana_gpt-4o_interference_non_key \
#     --text-only-base tasks/out/m3cot/test0/banana_gpt-4o_text_only \
#     --output eval/m3cot_test0_banana_gpt-4o_config.json

# python eval/create_config.py \
#     --solution-base golden/clevr_math/val/banana_gpt-4o \
#     --model-base tasks/out/clevr_math/val/banana_gpt-4o \
#     --perturbed-base tasks/out/clevr_math/val/banana_gpt-4o_interference_key \
#     --irrelevant-base tasks/out/clevr_math/val/banana_gpt-4o_interference_non_key \
#     --text-only-base tasks/out/clevr_math/val/banana_gpt-4o_text_only \
#     --output eval/clevr_math_val_banana_gpt-4o_config.json

python eval/create_config.py \
    --solution-base golden/math/code_gpt-4o \
    --model-base tasks/out/math/code_gpt-4o \
    --perturbed-base tasks/out/math/code_gpt-4o_interference_key \
    --irrelevant-base tasks/out/math/code_gpt-4o_interference_non_key \
    --text-only-base tasks/out/math/code_gpt-4o_text_only \
    --output eval/math_code_gpt-4o_config.json