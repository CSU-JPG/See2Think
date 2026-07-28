#!/bin/bash

# run bin/run.sh with logging
bash bin/run.sh | tee logs/run_$(date +%Y%m%d_%H%M%S).log