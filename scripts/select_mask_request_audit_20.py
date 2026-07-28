#!/usr/bin/env python3
import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

DATA_PREFIX = "annotation/dataset/data/"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def rel_source_dir(data_path: str) -> str:
    p = data_path.replace("\\", "/")
    if p.startswith(DATA_PREFIX):
        p = p[len(DATA_PREFIX):]
    if p.endswith("/data.json"):
        p = p[: -len("/data.json")]
    return p


def task_key(task: dict[str, Any]) -> str:
    return f"{rel_source_dir(task['path'])}::{int(task['id'])}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample 20 trajectories for request-payload mask auditing.")
    parser.add_argument("--audit-csv", default="outputs/human_audit/wrong_render_120/wrong_render_audit_120.csv")
    parser.add_argument("--tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    parser.add_argument("--output-dir", default="json/run_tasks_mask_request_audit_20")
    parser.add_argument("--seed", type=int, default=2026071302)
    parser.add_argument("--per-setting", type=int, default=10)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    task_by_key = {task_key(task): task for task in load_json(Path(args.tasks))}
    audit_rows = []
    with Path(args.audit_csv).open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["task_key"] not in task_by_key:
                raise KeyError(f"audit sample not in current 1200 manifest: {row['task_key']}")
            audit_rows.append(row)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for setting in ("vaot_full", "vaot_wrong_render"):
        selected = rng.sample(audit_rows, args.per_setting)
        by_model: dict[str, list[dict[str, Any]]] = {}
        for row in selected:
            model = row["model"]
            task = dict(task_by_key[row["task_key"]])
            task["_request_audit_setting"] = setting
            task["_request_audit_model"] = model
            task["_request_audit_task_key"] = row["task_key"]
            by_model.setdefault(model, []).append(task)
            manifest.append(
                {
                    "setting": setting,
                    "model": model,
                    "family": row["family"],
                    "task_key": row["task_key"],
                    "sample_id": int(row["sample_id"]),
                }
            )
        for model, tasks in sorted(by_model.items()):
            safe = model.replace(":", "-").replace("/", "_").replace("\\", "_")
            target = out_dir / setting / f"{safe}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{setting} {model}: {len(tasks)} -> {target}")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out_dir / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["setting", "model", "family", "task_key", "sample_id"])
        writer.writeheader()
        writer.writerows(manifest)
    print(f"total={len(manifest)} seed={args.seed} manifest={out_dir / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
