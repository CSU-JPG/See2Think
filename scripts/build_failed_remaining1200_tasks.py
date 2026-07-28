"""Build per-model task lists containing only failures from the last 1200 run."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "json" / "run_tasks_remaining_600"
LOG_DIR = ROOT / "newlogs"
OUTPUT_DIR = ROOT / "json" / "rerun_failed_remaining_600"

RUNS = (
    ("gpt-5.5", "text_cot"),
    ("gpt-5.5", "vaot_no_render"),
    ("gpt-5.5", "vaot_wrong_render"),
    ("o3", "text_cot"),
    ("o3", "vaot_no_render"),
    ("o3", "vaot_wrong_render"),
    ("gemini-3.5-flash", "text_cot"),
    ("gemini-3.5-flash", "vaot_no_render"),
    ("gemini-3.5-flash", "vaot_wrong_render"),
)


def failed_pairs(summary_path: Path) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("status") == "failed":
            pairs.add((entry["path"], int(entry["id"])))
    return pairs


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for model, setting in RUNS:
        run_dir = LOG_DIR / f"final1200_remaining_{model}_{setting}_0_600"
        summaries = sorted(run_dir.glob("summary_banana_*.log"))
        if len(summaries) != 1:
            raise RuntimeError(f"Expected one summary for {model}/{setting}, found {len(summaries)}")

        failures = failed_pairs(summaries[0])
        source_path = SOURCE_DIR / f"{model}__{setting}__remaining_600.json"
        source_tasks = json.loads(source_path.read_text(encoding="utf-8"))
        selected = [task for task in source_tasks if (task["path"], int(task["id"])) in failures]
        selected_pairs = {(task["path"], int(task["id"])) for task in selected}
        missing = failures - selected_pairs
        if missing:
            raise RuntimeError(f"Failures missing from {source_path}: {sorted(missing)[:5]}")

        output_path = OUTPUT_DIR / f"{model}__{setting}__failed.json"
        output_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total += len(selected)
        print(f"{model:24} {setting:20} {len(selected):4} -> {output_path.relative_to(ROOT)}")
    print(f"Total failed tasks selected: {total}")


if __name__ == "__main__":
    main()
