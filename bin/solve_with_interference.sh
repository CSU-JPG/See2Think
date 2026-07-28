#!/bin/bash

# python solve/auto_solve.py \
#     -p annotation/dataset/data/math/data.json \
#     -i 1 \
#     -o tasks/interference/math/1 \
#     -m code \
#     -M gpt-4o \
#     --golden golden/golden-3/math/code_gemini-2.5-pro/1/steps.md \
#     --interference modify_key

# python solve/auto_solve.py \
#     -p annotation/dataset/data/math/data.json \
#     -i 1 \
#     -o tasks/interference_non_key/math/1 \
#     -m code \
#     -M gpt-4o \
#     --golden golden/golden-3/math/code_gemini-2.5-pro/1/steps.md \
#     --interference modify_non_key

python solve/auto_solve.py \
    -p annotation/dataset/data/m3cot/test1/data.json \
    -i 4 \
    -o tasks/interference_non_key/m3cot/test1/4 \
    -m banana \
    -M gpt-4o \
    --golden golden/golden-3/m3cot/test1/banana_gemini-2.5-pro/4/steps.md \
    --interference modify_non_key