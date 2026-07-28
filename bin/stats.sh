#!/bin/bash

python convert/stats.py \
    --input-files \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_interference_key.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_interference_non_key.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_optional.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_text_only.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_use_depth.json" \
        "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_use_edge.json" \
    --output-file "${SEE2THINK_OUTPUT_BASE}/${MODEL_PATH_PREFIX}_stats.json"