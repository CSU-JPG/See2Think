#!/bin/bash

# range: 100,110 150,160 300,310 400,410
# iterate over different ranges using a for loop in bash

for range in "100,110" "150,160" "300,310" "400,410"; do
    python solve/check_question.py \
        --dataset m3cot/test1 \
        --model gpt-4o \
        --workers 10 \
        --range $range \
        --output tasks/check_question/m3cot_test1_$range.json
done