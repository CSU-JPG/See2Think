#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTING_META = {
    "text_cot": {
        "folder": "final1200_{model}_text_cot",
        "subdir": "banana_{model}_text_cot",
        "need_render": False,
    },
    "vaot_no_render": {
        "folder": "final1200_{model}_vaot_no_render",
        "subdir": "banana_{model}_vaot_no_render",
        "need_render": False,
    },
    "vaot_full": {
        "folder": "final1200_{model}_vaot_full_floor",
        "subdir": "banana_{model}_vaot_full",
        "need_render": False,
    },
    "vaot_wrong_render": {
        "folder": "final1200_{model}_vaot_wrong_render_floor",
        "subdir": "banana_{model}_vaot_wrong_render",
        "need_render": True,
    },
}


def dataset_rel(path: str) -> Path:
    parts = Path(path).parts
    try:
        i = parts.index("data")
        rel = parts[i + 1 :]
    except ValueError:
        rel = parts[-3:]
    if rel and rel[-1] == "data.json":
        rel = rel[:-1]
    return Path(*rel)


def latest_log_dir(model: str, setting: str, run_id: str | None) -> Path | None:
    safe = model.replace(":", "-")
    pattern = f"final1200_{safe}_{setting}_0_1200_*"
    dirs = sorted((ROOT / "newlogs").glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if run_id:
        dirs = [p for p in dirs if p.name.endswith(run_id)]
    return dirs[0] if dirs else None


def log_name(task: dict) -> str:
    task_name = "_".join(task["path"].split("/")[3:]).replace("data.json", "")
    return f"{task_name}_{task['id']}_*.log"


def classify_log(text: str) -> list[str]:
    reasons: list[str] = []
    if "[TIMEOUT]" in text or "Task timeout after" in text:
        reasons.append("timeout")
    if "Traceback" in text:
        reasons.append("traceback")
    if re.search(r"\bERROR\b|Task failed|failed for", text, re.I):
        reasons.append("error")
    if "Empty model response" in text:
        reasons.append("empty_model_response")
    if "Max retries reached" in text:
        reasons.append("max_retries")
    return reasons


def valid_steps(path: Path) -> tuple[bool, int]:
    if not path.exists():
        return False, 0
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) < 20:
        return False, len(text)
    return True, len(text)


def has_render_file(out_dir: Path) -> bool:
    if not out_dir.exists():
        return False
    for p in out_dir.glob("p*.png"):
        if p.name != "p0.png" and p.stat().st_size > 0:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    ap.add_argument("--model", default="qwen3-vl-32b-thinking")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    model = args.model
    safe = model.replace(":", "-")
    tasks = json.loads((ROOT / args.tasks).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "outputs" / "qwen3vl32b_failure_tracking"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for setting, meta in SETTING_META.items():
        output_root = ROOT / "newtasks" / meta["folder"].format(model=safe)
        logs = latest_log_dir(safe, setting, args.run_id)
        for order, task in enumerate(tasks):
            rel = dataset_rel(task["path"])
            task_out = output_root / rel / meta["subdir"].format(model=safe) / str(task["id"])
            steps = task_out / "steps.md"
            ok_steps, steps_chars = valid_steps(steps)
            reasons: list[str] = []
            if not task_out.exists():
                reasons.append("output_dir_missing")
            if not steps.exists():
                reasons.append("steps_missing")
            elif not ok_steps:
                reasons.append("steps_empty_or_too_short")
            if meta["need_render"] and not has_render_file(task_out):
                reasons.append("render_missing")

            log_file = ""
            log_reasons: list[str] = []
            if logs:
                matches = sorted(logs.glob(log_name(task)), key=lambda p: p.stat().st_mtime, reverse=True)
                if matches:
                    log_file = str(matches[0].relative_to(ROOT))
                    log_text = matches[0].read_text(encoding="utf-8", errors="replace")
                    log_reasons = classify_log(log_text)
                    reasons.extend(log_reasons)
                elif task_out.exists() and not ok_steps:
                    reasons.append("log_missing")

            # Do not call running but incomplete tasks "failed" unless there is evidence
            # of timeout/error or a stale empty output directory. The CSV is for tracking.
            status = "ok" if not reasons else "failed_or_incomplete"
            rows.append({
                "status": status,
                "setting": setting,
                "order": task.get("order", order),
                "category": task.get("category", ""),
                "target_task": task.get("target_task", ""),
                "source": task.get("source", ""),
                "path": task["path"],
                "id": task["id"],
                "output_dir": str(task_out.relative_to(ROOT)),
                "steps_chars": steps_chars,
                "log_file": log_file,
                "reasons": ";".join(dict.fromkeys(reasons)),
            })

    failed = [r for r in rows if r["status"] != "ok"]
    csv_path = out_dir / "qwen3vl32b_failed_or_incomplete.csv"
    json_path = out_dir / "qwen3vl32b_failed_or_incomplete.json"
    summary_path = out_dir / "qwen3vl32b_failure_summary.md"
    fields = list(rows[0])
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(failed)
    json_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")

    by_setting = Counter(r["setting"] for r in failed)
    by_reason = Counter()
    for r in failed:
        for reason in r["reasons"].split(";"):
            if reason:
                by_reason[reason] += 1
    lines = [
        "# Qwen3-VL-32B-Thinking failure / incomplete tracking",
        "",
        f"- Model: `{model}`",
        f"- Tasks: `{args.tasks}`",
        f"- Total expected runs: {len(tasks) * len(SETTING_META)}",
        f"- Failed or incomplete rows: {len(failed)}",
        "",
        "## By setting",
        "",
        "| Setting | Count |",
        "|---|---:|",
    ]
    lines += [f"| {k} | {v} |" for k, v in by_setting.most_common()]
    lines += ["", "## By reason", "", "| Reason | Count |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in by_reason.most_common()]
    lines += ["", f"- CSV: `{csv_path.relative_to(ROOT)}`", f"- JSON: `{json_path.relative_to(ROOT)}`"]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_path)
    print(csv_path)
    print(json_path)
    print(f"failed_or_incomplete={len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
