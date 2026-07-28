#! /bin/bash

MATH_SELECTED_FILES=$(find filter_and_modify/check_question/math -name "*.json")
python solve/extract_index.py --output "tasks/check_question/math.idx" $MATH_SELECTED_FILES

CLEVR_MATH_SELECTED_FILES=$(find filter_and_modify/check_question/clevr_math -name "*.json")
python solve/extract_index.py --output "tasks/check_question/clevr_math.idx" $CLEVR_MATH_SELECTED_FILES

COMMONSENSE_SELECTED_FILES=$(find filter_and_modify/check_question/test0 tasks/check_question/commonsense -name "*.json")
python solve/extract_index.py --output "tasks/check_question/commonsense.idx" $COMMONSENSE_SELECTED_FILES

SCIENCE_SELECTED_FILES=$(find filter_and_modify/check_question/test1 -name "*.json")
python solve/extract_index.py --output "tasks/check_question/science.idx" $SCIENCE_SELECTED_FILES

PRISM_SELECTED_FILES=$(find filter_and_modify/check_question/prism -name "*.json")
for f in $PRISM_SELECTED_FILES; do
  python solve/extract_index.py --output "${f%.json}.idx" "$f"
done
mkdir -p tasks/check_question/prism/
mv filter_and_modify/check_question/prism/*.idx tasks/check_question/prism/