import json
from collections import Counter, defaultdict
from pathlib import Path

STAMP = "20260725_150902"

ROOT = Path("neweval/results")

FULL_PATH = (
    ROOT
    / f"answer_qwen3vl32b_1200_{STAMP}_vaot_full"
    / "answer_judge.jsonl"
)

WRONG_PATH = (
    ROOT
    / f"answer_qwen3vl32b_1200_{STAMP}_vaot_wrong_render"
    / "answer_judge.jsonl"
)

def load(path: Path):
    rows = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            key = row.get("task_key")
            if not key:
                source = row.get("source", "")
                sample_id = row.get("sample_id", "")
                key = f"{source}::{sample_id}"

            rows[key] = row
    return rows

full = load(FULL_PATH)
wrong = load(WRONG_PATH)

common = sorted(set(full) & set(wrong))

overall = Counter()
by_task = defaultdict(Counter)

for key in common:
    a = bool(full[key].get("correct"))
    b = bool(wrong[key].get("correct"))

    if a and b:
        status = "correct_correct"
    elif a and not b:
        status = "correct_wrong"
    elif not a and b:
        status = "wrong_correct"
    else:
        status = "wrong_wrong"

    overall[status] += 1

    task = (
        full[key].get("target_task")
        or wrong[key].get("target_task")
        or "UNKNOWN"
    )
    by_task[task][status] += 1

print(f"VAoT rows       : {len(full)}")
print(f"WrongRender rows: {len(wrong)}")
print(f"Aligned rows    : {len(common)}")

print("\n===== Overall transitions =====")
for name in [
    "correct_correct",
    "correct_wrong",
    "wrong_correct",
    "wrong_wrong",
]:
    print(f"{name:16s}: {overall[name]}")

print("\n===== By task =====")
for task in sorted(by_task):
    c = by_task[task]
    net = c["wrong_correct"] - c["correct_wrong"]
    print(
        f"{task:20s} "
        f"VAoT对→WR错={c['correct_wrong']:3d}  "
        f"VAoT错→WR对={c['wrong_correct']:3d}  "
        f"净变化={net:+3d}"
    )
