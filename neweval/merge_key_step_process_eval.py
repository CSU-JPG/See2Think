#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from typing import Any


RUNS = [
    (
        "gpt-5.5",
        Path("neweval/results/gpt54_judge_gpt55_final1200_vaot_full/process_judge.jsonl"),
        Path("neweval/results/key_step_gpt55_final1200_vaot_full/key_step_judge.jsonl"),
        Path("neweval/results/process_eval_with_key_step_gpt55_final1200_vaot_full"),
    ),
    (
        "o3",
        Path("neweval/results/gpt54_judge_o3_final1200_vaot_full/process_judge.jsonl"),
        Path("neweval/results/key_step_o3_final1200_vaot_full/key_step_judge.jsonl"),
        Path("neweval/results/process_eval_with_key_step_o3_final1200_vaot_full"),
    ),
    (
        "gemini-3.5-flash",
        Path("neweval/results/gpt54_judge_gemini35flash_final1200_vaot_full/process_judge.jsonl"),
        Path("neweval/results/key_step_gemini35flash_final1200_vaot_full/key_step_judge.jsonl"),
        Path("neweval/results/process_eval_with_key_step_gemini35flash_final1200_vaot_full"),
    ),
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    judge = row.get("judge") or {}
    key = row.get("key_step_judge") or {}
    return {
        "task_key": row.get("task_key"),
        "model": row.get("model"),
        "setting": row.get("setting"),
        "category": row.get("category"),
        "target_task": row.get("target_task"),
        "relative_source_dir": row.get("relative_source_dir"),
        "sample_id": row.get("sample_id"),
        "key_steps": json.dumps(key.get("key_steps", []), ensure_ascii=False),
        "no_valid_visual_step": key.get("no_valid_visual_step"),
        "key_step_reason": key.get("reason", ""),
        "action_relevance": (judge.get("action_relevance") or {}).get("normalized_score"),
        "action_relevance_reason": (judge.get("action_relevance") or {}).get("reason", ""),
        "render_faithfulness": (judge.get("render_faithfulness") or {}).get("normalized_score"),
        "render_faithfulness_reason": (judge.get("render_faithfulness") or {}).get("reason", ""),
        "feedback_uptake": (judge.get("feedback_uptake") or {}).get("normalized_score"),
        "feedback_uptake_reason": (judge.get("feedback_uptake") or {}).get("reason", ""),
        "overall_failure_source": judge.get("overall_failure_source"),
        "summary": judge.get("summary"),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(flatten(rows[0]).keys()) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten(row))


def summarize(rows: list[dict[str, Any]], missing_key_steps: list[str]) -> dict[str, Any]:
    metrics = ["action_relevance", "render_faithfulness", "feedback_uptake"]
    out: dict[str, Any] = {
        "count": len(rows),
        "missing_key_step_count": len(missing_key_steps),
        "missing_key_steps": missing_key_steps,
        "key_step_selected_count": 0,
        "key_step_no_valid_count": 0,
        "key_step_avg_selected_steps": None,
        "process_metric_averages": {},
    }
    total_key_steps = 0
    for row in rows:
        key = row.get("key_step_judge") or {}
        if key.get("no_valid_visual_step") is True:
            out["key_step_no_valid_count"] += 1
        else:
            out["key_step_selected_count"] += 1
        total_key_steps += len(key.get("key_steps") or [])
    out["key_step_avg_selected_steps"] = round(total_key_steps / len(rows), 4) if rows else None
    for metric in metrics:
        values = [
            ((row.get("judge") or {}).get(metric) or {}).get("normalized_score")
            for row in rows
        ]
        values = [v for v in values if isinstance(v, (int, float))]
        out["process_metric_averages"][metric] = round(sum(values) / len(values), 4) if values else None
    return out


def main() -> int:
    for _, process_path, key_path, out_dir in RUNS:
        process_rows = [row for row in load_jsonl(process_path) if row.get("status") == "ok"]
        key_rows = {row.get("task_key"): row for row in load_jsonl(key_path) if row.get("status") == "ok"}
        merged = []
        missing = []
        for row in process_rows:
            key = key_rows.get(row.get("task_key"))
            if not key:
                missing.append(row.get("task_key"))
                continue
            out = dict(row)
            out["key_step_judge"] = {
                "visual_steps": key.get("visual_steps", []),
                "key_steps": key.get("key_steps", []),
                "no_valid_visual_step": key.get("no_valid_visual_step", False),
                "reason": key.get("reason", ""),
                "judge_model": key.get("key_step_judge_model"),
            }
            merged.append(out)
        write_jsonl(out_dir / "process_eval_with_key_step.jsonl", merged)
        write_csv(out_dir / "process_eval_with_key_step.csv", merged)
        write_json(out_dir / "summary.json", summarize(merged, missing))
        print(out_dir, len(merged), "missing", len(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
