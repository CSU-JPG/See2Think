"""Build per-setting failed/incomplete task lists for Qwen reruns.

This script is intentionally conservative: a case is complete only when
`steps.md` exists, is non-trivial, and contains a final-answer marker.  Partial
VAoT traces, empty responses, and directories that only contain q.md/p0.png are
marked for rerun.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


FINAL_MARKER = re.compile(
    r"(final\s+answer|final_answer|answer\s*:|\\boxed|最终答案|答案)",
    re.IGNORECASE,
)
ERROR_MARKER = re.compile(
    r"(traceback|apiconnectionerror|connecterror|runtimeerror|empty model response|timeout|timed out|request failed)",
    re.IGNORECASE,
)


SETTINGS = {
    "text_cot": "text_cot",
    "vaot_no_render": "vaot_no_render",
    "vaot_full": "vaot_full_floor",
    "vaot_wrong_render": "vaot_wrong_render_floor",
}


def dataset_parts(task_path: str) -> Path:
    parts = [p for p in Path(task_path).parts if p and p not in {"/", "\\"}]
    if parts and parts[-1] == "data.json":
        parts = parts[:-1]
    if "data" in parts:
        idx = parts.index("data")
        tail = parts[idx + 1 :]
        return Path(*tail) if tail else Path("unknown")
    return Path(*parts[-2:]) if len(parts) >= 2 else Path(parts[-1] if parts else "unknown")


def output_dir(root: Path, task: dict, model: str, setting: str) -> Path:
    return root / dataset_parts(task["path"]) / f"banana_{model}_{setting}" / str(task["id"])


def completion_status(case_dir: Path, setting: str) -> tuple[bool, str, int]:
    q = case_dir / "q.md"
    p0 = case_dir / "p0.png"
    steps = case_dir / "steps.md"
    if not q.is_file():
        return False, "missing_q", 0
    if not p0.is_file():
        return False, "missing_p0", 0
    if not steps.is_file():
        return False, "missing_steps", 0
    size = steps.stat().st_size
    if size < 100:
        return False, "empty_or_too_short_steps", size
    text = steps.read_text(encoding="utf-8", errors="ignore")
    if ERROR_MARKER.search(text):
        return False, "error_marker_in_steps", size
    if not FINAL_MARKER.search(text):
        return False, "missing_final_answer_marker", size
    return True, "complete", size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    parser.add_argument("--model", default="qwen3-vl-32b-thinking")
    parser.add_argument("--newtasks-root", default="newtasks")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    tasks_path = Path(args.tasks)
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    summary_rows: list[dict] = []

    for setting, suffix in SETTINGS.items():
        root = Path(args.newtasks_root) / f"final1200_{args.model}_{suffix}"
        failed_tasks: list[dict] = []
        complete = 0

        for task in tasks:
            case_dir = output_dir(root, task, args.model, setting)
            ok, reason, steps_bytes = completion_status(case_dir, setting)
            if ok:
                complete += 1
                continue
            failed_tasks.append(task)
            all_rows.append(
                {
                    "setting": setting,
                    "task_path": task.get("path", ""),
                    "task_id": task.get("id", ""),
                    "reason": reason,
                    "steps_bytes": steps_bytes,
                    "output_dir": str(case_dir),
                }
            )

        failed_path = out_dir / f"failed_{setting}.json"
        failed_path.write_text(json.dumps(failed_tasks, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_rows.append(
            {
                "setting": setting,
                "complete": complete,
                "failed_or_incomplete": len(failed_tasks),
                "total": len(tasks),
                "failed_tasks_json": str(failed_path),
            }
        )

    with (out_dir / "failed_cases.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["setting", "task_path", "task_id", "reason", "steps_bytes", "output_dir"],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["setting", "complete", "failed_or_incomplete", "total", "failed_tasks_json"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(json.dumps({"summary": summary_rows, "failed_cases": str(out_dir / "failed_cases.csv")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
