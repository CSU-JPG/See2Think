#!/bin/sh
# Run the existing semantic answer-change judge with credentials from config.sh.
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
. ./config.sh

PYTHON_EXE="${SEE2THINK_WINDOWS_PYTHON:-E:/pythonuse/python.exe}"
exec "$PYTHON_EXE" eval/answer_change_judge.py "$@"
