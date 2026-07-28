#!/usr/bin/env python3
import argparse
import csv
import json
import re
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


def task_key_from_task(task: dict[str, Any]) -> str:
    return f"{rel_source_dir(task['path'])}::{int(task['id'])}"


def sample_question(sample: dict[str, Any]) -> str:
    for key in ("question", "modified_question", "problem", "query", "prompt"):
        value = sample.get(key)
        if value:
            return str(value)
    return ""


def sample_answer(sample: dict[str, Any]) -> str:
    for key in ("answer", "modified_answer", "ground_truth", "gt_answer", "target"):
        value = sample.get(key)
        if value is not None:
            return str(value)
    return ""


def extract_final_answer(steps_text: str) -> str:
    matches = list(
        re.finditer(
            r"\*\*Final Answer:\*\*\s*(.*?)(?=\n\*\*Step|\Z)",
            steps_text,
            re.DOTALL | re.IGNORECASE,
        )
    )
    if matches:
        return matches[-1].group(1).strip()
    marker = "Final Answer:"
    idx = steps_text.lower().rfind(marker.lower())
    if idx >= 0:
        return steps_text[idx + len(marker):].strip()
    return ""


def load_data_cache(data_base: Path, data_path: str, cache: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if data_path not in cache:
        cache[data_path] = load_json(data_base / data_path)
    return cache[data_path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build answer-judge input JSONL from final_results manifests")
    parser.add_argument("--tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    parser.add_argument("--data-base", default=".")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--setting", required=True)
    args = parser.parse_args()

    data_base = Path(args.data_base)
    tasks = load_json(Path(args.tasks))
    task_by_key = {task_key_from_task(task): task for task in tasks}
    data_cache: dict[str, list[dict[str, Any]]] = {}

    out_path = Path(args.output_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    missing_steps = 0
    with Path(args.manifest).open("r", encoding="utf-8-sig", newline="") as f, out_path.open("w", encoding="utf-8") as out:
        reader = csv.DictReader(f)
        for row in reader:
            # A WrongRender response can have a valid textual final answer
            # even when the rendering artifact is absent.  It remains valid
            # for answer accuracy; process metrics handle render coverage
            # separately.
            if row.get("status") not in {"ok", "missing_render"}:
                continue
            rel = row["relative_source_dir"].replace("\\", "/")
            sample_id = int(row["sample_id"])
            key = f"{rel}::{sample_id}"
            task = task_by_key.get(key)
            if task is None:
                # ``--tasks`` may intentionally name a subset (for example,
                # the complementary 600 of a 1,200-task run).  In that case
                # do not silently score every row from the manifest.
                continue
            target_dir = Path(row["target_dir"])
            steps_path = target_dir / "steps.md"
            if not steps_path.exists():
                missing_steps += 1
                continue
            sample = load_data_cache(data_base, task["path"], data_cache)[int(task["id"])]
            steps_text = steps_path.read_text(encoding="utf-8", errors="ignore")
            obj = {
                "status": "ok",
                "task_key": key,
                "model": args.model,
                "setting": args.setting,
                "category": task.get("category", ""),
                "target_task": task.get("target_task", ""),
                "source": task.get("source", ""),
                "relative_source_dir": rel,
                "path": task["path"],
                "sample_id": sample_id,
                "output_dir": str(target_dir),
                "steps_md": str(steps_path),
                "question": sample_question(sample),
                "ground_truth": sample_answer(sample),
                "final_answer": extract_final_answer(steps_text),
            }
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1
    print(f"wrote {count} rows to {out_path}; missing_steps={missing_steps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
