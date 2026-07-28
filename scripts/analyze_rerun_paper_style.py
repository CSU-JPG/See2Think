"""Create paper-style outcome and process analyses for the latest rerun.

The current rerun supplies answer judgments for CoT, NoRender, and
WrongRender.  VAoT-Full trajectories were unchanged, so their existing aligned
600-sample answer judgments are joined with the newly completed key-step metric
evaluation.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "neweval" / "results"
LOGS = ROOT / "newlogs"

MODELS = (
    ("gpt-5.5", "gpt55", "answer_gpt55_final600subset_vaot_full"),
    ("o3", "o3", "answer_o3_final600subset_vaot_full"),
    ("gemini-3.5-flash", "gemini35flash", "answer_gemini35flash_final600subset_vaot_full"),
)
SETTINGS = ("text_only", "no_render", "full", "wrong_render")
CATEGORIES = ("2D", "3D", "Real")

# Paper Table 1 taxonomy. Do not use the benchmark record's coarse ``category``
# field: its grouping differs from the paper's task-family split.
PAPER_CATEGORY_BY_SOURCE_DIR = {
    "math": "2D", "emma/math": "2D", "emma/physics": "2D",
    "emma/chemistry": "2D", "m3cot/test1": "2D", "prism": "2D",
    "clevr_math/val": "3D", "super_clevr": "3D",
    "VLABench": "Real", "droid": "Real", "m3cot/test0": "Real",
    "intphy2": "Real",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def latest_run_manifest() -> tuple[Path, dict[str, Any]]:
    runs = sorted(LOGS.glob("acc_eval_rerun_*"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not runs:
        raise RuntimeError("No acc_eval_rerun manifest found")
    manifest = json.loads((runs[0] / "manifest.json").read_text(encoding="utf-8-sig"))
    return runs[0], manifest


def normalize_model(model: str) -> str:
    return model.replace(":stable", "-stable")


def canonical_category(row: dict[str, Any]) -> str:
    rel = str(row.get("relative_source_dir") or "").replace("\\", "/")
    if rel not in PAPER_CATEGORY_BY_SOURCE_DIR:
        raise RuntimeError(f"Unknown paper task family: {rel!r}")
    return PAPER_CATEGORY_BY_SOURCE_DIR[rel]


def row_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["task_key"]): row for row in rows if row.get("status") == "ok"}


def grouped_accuracy(rows: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "ok":
            groups[tuple(row.get(field, "") for field in group_fields)].append(row)
    out = []
    for key, group in sorted(groups.items()):
        correct = sum(bool(row.get("correct")) for row in group)
        item = dict(zip(group_fields, key))
        item.update(count=len(group), correct=correct, accuracy=round(correct / len(group), 4))
        out.append(item)
    return out


def process_table(process_rows: list[dict[str, Any]], full_answers: dict[str, dict[str, Any]], model: str) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    missing_answers: list[str] = []
    for row in process_rows:
        if row.get("status") != "ok":
            continue
        answer = full_answers.get(str(row.get("task_key")))
        if answer is None:
            missing_answers.append(str(row.get("task_key")))
            continue
        label = "Correct" if answer.get("correct") else "Incorrect"
        groups[(label, str(row.get("category", "")))].append(row)
    if missing_answers:
        raise RuntimeError(f"{model}: {len(missing_answers)} process rows have no Full answer judgment")

    out: list[dict[str, Any]] = []
    for answer in ("Correct", "Incorrect"):
        for category in CATEGORIES:
            group = groups.get((answer, category), [])
            if not group:
                continue
            out.append({
                "model": model,
                "answer": answer,
                "category": category,
                "count": len(group),
                "action": round(mean(float(row["action_relevance"]) for row in group), 4),
                "render": round(mean(float(row["render_faithfulness"]) for row in group), 4),
                "feedback": round(mean(float(row["feedback_uptake"]) for row in group), 4),
            })
    return out


def paired_rows(model: str, category: str, left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]], comparison: str) -> dict[str, Any]:
    keys = sorted(set(left) & set(right))
    rows = [key for key in keys if left[key].get("category") == category and right[key].get("category") == category]
    left_correct = sum(bool(left[key].get("correct")) for key in rows)
    right_correct = sum(bool(right[key].get("correct")) for key in rows)
    benefit = sum(not bool(left[key].get("correct")) and bool(right[key].get("correct")) for key in rows)
    harm = sum(bool(left[key].get("correct")) and not bool(right[key].get("correct")) for key in rows)
    return {
        "model": model,
        "category": category,
        "comparison": comparison,
        "count": len(rows),
        "left_accuracy": round(left_correct / len(rows), 4),
        "right_accuracy": round(right_correct / len(rows), 4),
        "accuracy_delta_right_minus_left": round((right_correct - left_correct) / len(rows), 4),
        "left_incorrect_to_right_correct": benefit,
        "left_correct_to_right_incorrect": harm,
        "net_transition": round((benefit - harm) / len(rows), 4),
    }


def main() -> None:
    run_dir, manifest = latest_run_manifest()
    run_id = run_dir.name.removeprefix("acc_eval_rerun_")
    output = ROOT / "outputs" / f"paper_style_analysis_{run_id}"
    output.mkdir(parents=True, exist_ok=True)

    record_by_key = {(record["type"], normalize_model(record["model"]), record["setting"]): record for record in manifest["records"]}
    all_answers: dict[str, dict[str, dict[str, Any]]] = {}
    all_answer_rows: list[dict[str, Any]] = []
    process_by_model: dict[str, list[dict[str, Any]]] = {}

    for model, tag, historic_full_run in MODELS:
        setting_maps: dict[str, dict[str, Any]] = {}
        for setting in ("text_only", "no_render", "wrong_render"):
            record = record_by_key[("accuracy", model, setting)]
            rows = load_jsonl(RESULTS / record["run_name"] / "answer_judge.jsonl")
            if len(rows) != 600:
                raise RuntimeError(f"{model}/{setting}: expected 600 answer rows, found {len(rows)}")
            for row in rows:
                row["model"] = model
                row["setting"] = setting
                row["category"] = canonical_category(row)
            setting_maps[setting] = row_map(rows)
            all_answer_rows.extend(rows)

        full_rows = load_jsonl(RESULTS / historic_full_run / "answer_judge.jsonl")
        if len(full_rows) != 600:
            raise RuntimeError(f"{model}/full: expected 600 historic answer rows, found {len(full_rows)}")
        for row in full_rows:
            row["model"] = model
            row["setting"] = "full"
            row["category"] = canonical_category(row)
        setting_maps["full"] = row_map(full_rows)
        all_answer_rows.extend(full_rows)
        all_answers[model] = setting_maps

        record = record_by_key[("process_eval", model, "full")]
        process_rows = load_jsonl(RESULTS / record["run_name"] / "key_step_metric_judge.jsonl")
        if len(process_rows) != 600:
            raise RuntimeError(f"{model}: expected 600 process rows, found {len(process_rows)}")
        for row in process_rows:
            row["category"] = canonical_category(row)
        process_by_model[model] = process_rows

    accuracy_model_setting_category = grouped_accuracy(all_answer_rows, ("model", "setting", "category"))
    accuracy_model_setting = grouped_accuracy(all_answer_rows, ("model", "setting"))
    accuracy_setting_category = grouped_accuracy(all_answer_rows, ("setting", "category"))
    write_csv(output / "accuracy_by_model_setting_category.csv", accuracy_model_setting_category)
    write_csv(output / "accuracy_by_model_setting_overall.csv", accuracy_model_setting)
    write_csv(output / "accuracy_by_setting_category_all_models.csv", accuracy_setting_category)

    process_rows_out: list[dict[str, Any]] = []
    process_overall_rows: list[dict[str, Any]] = []
    for model, _, _ in MODELS:
        process_rows_out.extend(process_table(process_by_model[model], all_answers[model]["full"], model))
        for category in (*CATEGORIES, "Overall"):
            group = [row for row in process_by_model[model] if category == "Overall" or row.get("category") == category]
            process_overall_rows.append({
                "model": model,
                "category": category,
                "count": len(group),
                "action": round(mean(float(row["action_relevance"]) for row in group), 4),
                "render": round(mean(float(row["render_faithfulness"]) for row in group), 4),
                "feedback": round(mean(float(row["feedback_uptake"]) for row in group), 4),
            })
    write_csv(output / "process_by_model_answer_category.csv", process_rows_out)
    write_csv(output / "process_by_model_category.csv", process_overall_rows)

    transitions: list[dict[str, Any]] = []
    for model, _, _ in MODELS:
        for category in CATEGORIES:
            transitions.append(paired_rows(model, category, all_answers[model]["no_render"], all_answers[model]["full"], "NoRender_to_Full"))
            transitions.append(paired_rows(model, category, all_answers[model]["full"], all_answers[model]["wrong_render"], "Full_to_WrongRender"))
    write_csv(output / "paired_intervention_transitions.csv", transitions)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "acc_eval_run": str(run_dir.relative_to(ROOT)),
        "answer_rows": len(all_answer_rows),
        "process_rows": sum(len(rows) for rows in process_by_model.values()),
        "files": [
            "accuracy_by_model_setting_category.csv",
            "accuracy_by_model_setting_overall.csv",
            "accuracy_by_setting_category_all_models.csv",
            "process_by_model_answer_category.csv",
            "process_by_model_category.csv",
            "paired_intervention_transitions.csv",
        ],
        "full_answer_source": {model: run for model, _, run in MODELS},
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
