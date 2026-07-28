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


def load_sample(data_base: Path, task: dict[str, Any], cache: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    data_path = task["path"]
    if data_path not in cache:
        cache[data_path] = load_json(data_base / data_path)
    return cache[data_path][int(task["id"])]


def output_dir_for(root: Path, model: str, setting: str, rel: str, sample_id: int) -> Path:
    return root / f"masked_action_audit120_{model}_{setting}_floor" / Path(*rel.split("/")) / f"banana_{model}_{setting}" / str(sample_id)


def make_answer_row(
    *,
    data_base: Path,
    task: dict[str, Any],
    audit_row: dict[str, str],
    setting: str,
    root: Path,
    data_cache: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], str | None]:
    model = audit_row["model"]
    rel = audit_row["relative_source_dir"].replace("\\", "/")
    sample_id = int(audit_row["sample_id"])
    out_dir = output_dir_for(root, model, setting, rel, sample_id)
    steps_path = out_dir / "steps.md"
    if not steps_path.exists():
        return {}, str(steps_path)

    sample = load_sample(data_base, task, data_cache)
    steps_text = steps_path.read_text(encoding="utf-8", errors="ignore")
    return {
        "status": "ok",
        "task_key": f"{rel}::{sample_id}",
        "model": model,
        "setting": f"masked_action_{setting}",
        "family": audit_row.get("family", ""),
        "category": task.get("category", ""),
        "target_task": task.get("target_task", ""),
        "source": task.get("source", ""),
        "relative_source_dir": rel,
        "path": task["path"],
        "sample_id": sample_id,
        "output_dir": str(out_dir),
        "steps_md": str(steps_path),
        "question": sample_question(sample),
        "ground_truth": sample_answer(sample),
        "final_answer": extract_final_answer(steps_text),
    }, None


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build answer-judge inputs for masked-action WrongRender audit 120 runs.")
    parser.add_argument("--audit-csv", default="outputs/human_audit/wrong_render_120/wrong_render_audit_120.csv")
    parser.add_argument("--tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    parser.add_argument("--data-base", default=".")
    parser.add_argument("--newtasks-root", default="newtasks")
    parser.add_argument("--output-dir", default="neweval/results/answer_inputs")
    args = parser.parse_args()

    data_base = Path(args.data_base)
    root = Path(args.newtasks_root)
    out_dir = Path(args.output_dir)
    tasks = load_json(Path(args.tasks))
    task_by_key = {task_key_from_task(task): task for task in tasks}
    data_cache: dict[str, list[dict[str, Any]]] = {}

    rows_by_setting: dict[str, list[dict[str, Any]]] = {
        "vaot_full": [],
        "vaot_wrong_render": [],
    }
    missing: list[dict[str, str]] = []

    with Path(args.audit_csv).open("r", encoding="utf-8-sig", newline="") as f:
        for audit_row in csv.DictReader(f):
            rel = audit_row["relative_source_dir"].replace("\\", "/")
            sample_id = int(audit_row["sample_id"])
            key = f"{rel}::{sample_id}"
            task = task_by_key.get(key)
            if task is None:
                raise KeyError(f"audit sample is not in current 1200 task manifest: {key}")
            for setting in rows_by_setting:
                row, missing_path = make_answer_row(
                    data_base=data_base,
                    task=task,
                    audit_row=audit_row,
                    setting=setting,
                    root=root,
                    data_cache=data_cache,
                )
                if missing_path:
                    missing.append({"task_key": key, "model": audit_row["model"], "setting": setting, "missing_steps": missing_path})
                else:
                    rows_by_setting[setting].append(row)

    full_path = out_dir / "masked_action_audit120_full.jsonl"
    wrong_path = out_dir / "masked_action_audit120_wrong_render.jsonl"
    write_jsonl(full_path, rows_by_setting["vaot_full"])
    write_jsonl(wrong_path, rows_by_setting["vaot_wrong_render"])

    missing_path = out_dir / "masked_action_audit120_missing.json"
    missing_path.write_text(json.dumps(missing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(rows_by_setting['vaot_full'])} rows to {full_path}")
    print(f"wrote {len(rows_by_setting['vaot_wrong_render'])} rows to {wrong_path}")
    print(f"missing={len(missing)} details={missing_path}")
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
