import json
from collections import defaultdict
from pathlib import Path

stamp = "20260725_150902"
root = Path("eval/results")

settings = [
    "text_cot",
    "vaot_no_render",
    "vaot_full",
    "vaot_wrong_render",
]

for setting in settings:
    path = (
        root
        / f"answer_qwen3vl32b_1200_{stamp}_{setting}"
        / "answer_judge.jsonl"
    )

    groups = defaultdict(lambda: [0, 0])

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            category = row.get("target_task", "")
            groups[category][1] += 1
            groups[category][0] += int(bool(row.get("correct")))

    print(f"\n===== {setting} =====")
    for category, (correct, total) in sorted(groups.items()):
        acc = 100 * correct / total if total else 0
        print(
            f"{category:25s} "
            f"{correct:3d}/{total:3d} "
            f"{acc:6.2f}%"
        )
