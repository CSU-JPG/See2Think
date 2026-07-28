#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    judge = row.get("judge") or {}
    key = judge.get("key_step_selection") or {}
    action = judge.get("action_relevance") or {}
    render = judge.get("render_faithfulness") or {}
    uptake = judge.get("feedback_uptake") or {}
    return {
        "task_key": row.get("task_key"),
        "model": row.get("model"),
        "setting": row.get("setting"),
        "category": row.get("category"),
        "target_task": row.get("target_task"),
        "source": row.get("source"),
        "relative_source_dir": row.get("relative_source_dir"),
        "sample_id": row.get("sample_id"),
        "key_steps": json.dumps(key.get("key_steps", []), ensure_ascii=False),
        "no_valid_visual_step": key.get("no_valid_visual_step"),
        "key_step_reason": key.get("reason"),
        "action_score": action.get("score"),
        "action_norm": action.get("normalized_score"),
        "render_score": render.get("score"),
        "render_norm": render.get("normalized_score"),
        "uptake_score": uptake.get("score"),
        "uptake_norm": uptake.get("normalized_score"),
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


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def summarize(rows: list[dict[str, Any]], missing_key_steps: list[str]) -> dict[str, Any]:
    metrics = ["action_relevance", "render_faithfulness", "feedback_uptake"]
    out: dict[str, Any] = {
        "count": len(rows),
        "missing_key_step_count": len(missing_key_steps),
        "missing_key_steps": missing_key_steps,
        "key_step_selection": {
            "selected_count": sum(1 for row in rows if not row.get("judge", {}).get("key_step_selection", {}).get("no_valid_visual_step")),
            "no_valid_visual_step_count": sum(1 for row in rows if row.get("judge", {}).get("key_step_selection", {}).get("no_valid_visual_step") is True),
        },
        "process_metric_means": {},
    }
    for metric in metrics:
        vals = [
            row.get("judge", {}).get(metric, {}).get("normalized_score")
            for row in rows
            if isinstance(row.get("judge", {}).get(metric, {}).get("normalized_score"), (int, float))
        ]
        out["process_metric_means"][metric] = mean(vals)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge key-step judge with process judge into complete Full eval.")
    parser.add_argument("--process-jsonl", required=True)
    parser.add_argument("--key-step-jsonl", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output-root", default="neweval/results")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    process_rows = [row for row in load_jsonl(Path(args.process_jsonl)) if row.get("status") == "ok"]
    key_rows = {row.get("task_key"): row for row in load_jsonl(Path(args.key_step_jsonl)) if row.get("status") == "ok"}

    merged: list[dict[str, Any]] = []
    missing: list[str] = []
    for row in process_rows:
        task_key = row.get("task_key")
        key = key_rows.get(task_key)
        if not key:
            missing.append(str(task_key))
            key_judge = {
                "key_steps": [],
                "no_valid_visual_step": None,
                "reason": "Key-step judge missing.",
                "visual_steps": [],
            }
        else:
            key_judge = {
                "key_steps": key.get("key_steps", []),
                "no_valid_visual_step": key.get("no_valid_visual_step"),
                "reason": key.get("reason", ""),
                "visual_steps": key.get("visual_steps", []),
            }
        judge = dict(row.get("judge") or {})
        judge["key_step_selection"] = key_judge
        merged.append({**row, "judge": judge})

    out_dir = Path(args.output_root) / args.run_name
    write_jsonl(out_dir / "complete_process_judge.jsonl", merged)
    write_csv(out_dir / "complete_process_judge.csv", merged)
    write_json(out_dir / "summary.json", summarize(merged, missing))
    print(f"merged={len(merged)} missing_key_steps={len(missing)} output={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
