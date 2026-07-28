import json
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

    if not path.exists():
        print(f"{setting:20s} MISSING FILE")
        continue

    total = 0
    correct = 0
    invalid = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except Exception:
                invalid += 1
                continue

            total += 1
            correct += int(bool(row.get("correct")))

    acc = 100 * correct / total if total else 0

    print(
        f"{setting:20s} "
        f"total={total:4d} "
        f"correct={correct:4d} "
        f"acc={acc:6.2f}% "
        f"invalid={invalid}"
    )
