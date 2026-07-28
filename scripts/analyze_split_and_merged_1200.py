"""Paper-style analyses for historical 600, complementary 600, and merged 1200.

The merge is keyed by ``task_key``.  It therefore preserves exact category
counts and never treats two separate 600-sample means as an unweighted average.
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
RESULTS = ROOT / "eval" / "results"
OUT = ROOT / "outputs" / "analysis_split_and_merged_1200"
MODELS = (
    ("gpt-5.5", "gpt55"),
    ("o3", "o3"),
    ("gemini-3.5-flash", "gemini35flash"),
)
SETTINGS = ("text_only", "no_render", "full", "wrong_render")
CATEGORIES = ("2D", "3D", "Real")

# Paper Table 1 taxonomy: group the 12 task families, rather than using the
# coarse category field carried by individual dataset records.
PAPER_CATEGORY_BY_SOURCE_DIR = {
    "math": "2D",                 # Geo
    "emma/math": "2D",            # Puzzle
    "emma/physics": "2D",         # Phys
    "emma/chemistry": "2D",       # Chem
    "m3cot/test1": "2D",          # Sci
    "prism": "2D",                # Prism
    "clevr_math/val": "3D",       # CLEVR
    "super_clevr": "3D",          # S-CLEVR
    "VLABench": "Real",           # VLA
    "droid": "Real",              # DROID
    "m3cot/test0": "Real",        # Comm.
    "intphy2": "Real",            # IntPhys
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def paper_category(row: dict[str, Any]) -> str:
    rel = str(row.get("relative_source_dir") or "").replace("\\", "/")
    if rel not in PAPER_CATEGORY_BY_SOURCE_DIR:
        raise RuntimeError(f"Unknown paper task family: {rel!r}")
    return PAPER_CATEGORY_BY_SOURCE_DIR[rel]


def ready_rows(path: Path, expected: int) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    if len(rows) != expected:
        raise RuntimeError(f"{path}: expected {expected} rows, found {len(rows)}")
    for row in rows:
        row["category"] = paper_category(row)
    return rows


def map_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped = {str(row["task_key"]): row for row in rows if row.get("status") == "ok"}
    if len(mapped) != len(rows):
        raise RuntimeError("Non-ok or duplicate answer rows encountered")
    return mapped


def latest_completed_answer(tag: str, setting: str) -> Path:
    candidates = []
    suffix = f"_{tag}_{setting}"
    for folder in RESULTS.glob(f"answer_complement600_*{suffix}"):
        path = folder / "answer_judge.jsonl"
        if path.exists() and len(load_jsonl(path)) == 600:
            candidates.append(path)
    if not candidates:
        raise RuntimeError(f"No completed complementary answer result for {tag}/{setting}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def old_answer_path(tag: str, setting: str) -> Path:
    return RESULTS / f"answer_{tag}_{setting}_600" / "answer_judge.jsonl"


def full_answer_path(tag: str) -> Path:
    return RESULTS / f"answer_{tag}_final1200_vaot_full" / "answer_judge.jsonl"


def old_process_path(tag: str) -> Path:
    return RESULTS / f"key_step_metric_{tag}_final600_vaot_full" / "key_step_metric_judge.jsonl"


def new_process_path(tag: str) -> Path:
    paths = []
    for folder in RESULTS.glob(f"key_step_metric_complement600_*_{tag}_full"):
        path = folder / "key_step_metric_judge.jsonl"
        if path.exists() and len(load_jsonl(path)) == 600:
            paths.append(path)
    if not paths:
        raise RuntimeError(f"Complementary Full process eval for {tag} is not complete")
    return max(paths, key=lambda item: item.stat().st_mtime)


def accuracy_tables(answer_sets: dict[str, dict[str, list[dict[str, Any]]]]) -> tuple[list[dict], list[dict], list[dict]]:
    detailed: list[dict] = []
    overall: list[dict] = []
    pooled: list[dict] = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for model, settings in answer_sets.items():
        for setting, rows in settings.items():
            for row in rows:
                groups[(model, setting, row["category"])].append(row)
    for (model, setting, cat), rows in sorted(groups.items()):
        correct = sum(bool(row["correct"]) for row in rows)
        detailed.append({"model": model, "setting": setting, "category": cat, "count": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 4)})
    groups2: dict[tuple, list[dict]] = defaultdict(list)
    groups3: dict[tuple, list[dict]] = defaultdict(list)
    for row in detailed:
        # Use raw answer rows rather than averaging category accuracies.
        pass
    for model, settings in answer_sets.items():
        for setting, rows in settings.items():
            groups2[(model, setting)].extend(rows)
            for row in rows:
                groups3[(setting, row["category"])].append(row)
    for (model, setting), rows in sorted(groups2.items()):
        correct = sum(bool(row["correct"]) for row in rows)
        overall.append({"model": model, "setting": setting, "count": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 4)})
    for (setting, cat), rows in sorted(groups3.items()):
        correct = sum(bool(row["correct"]) for row in rows)
        pooled.append({"setting": setting, "category": cat, "count": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 4)})
    return detailed, overall, pooled


def process_tables(process_sets: dict[str, list[dict[str, Any]]], full_answers: dict[str, list[dict[str, Any]]]) -> tuple[list[dict], list[dict]]:
    detailed: list[dict] = []
    overall: list[dict] = []
    for model, rows in process_sets.items():
        answers = map_rows(full_answers[model])
        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            if row.get("status") != "ok":
                continue
            row["category"] = paper_category(row)
            answer = answers.get(str(row["task_key"]))
            if answer is None:
                raise RuntimeError(f"{model}: process row missing matching Full answer")
            groups[("Correct" if answer["correct"] else "Incorrect", row["category"])].append(row)
        for answer in ("Correct", "Incorrect"):
            for cat in CATEGORIES:
                group = groups.get((answer, cat), [])
                if group:
                    detailed.append({"model": model, "answer": answer, "category": cat, "count": len(group), "action": round(mean(float(x["action_relevance"]) for x in group), 4), "render": round(mean(float(x["render_faithfulness"]) for x in group), 4), "feedback": round(mean(float(x["feedback_uptake"]) for x in group), 4)})
        for cat in (*CATEGORIES, "Overall"):
            group = [x for x in rows if x.get("status") == "ok" and (cat == "Overall" or paper_category(x) == cat)]
            overall.append({"model": model, "category": cat, "count": len(group), "action": round(mean(float(x["action_relevance"]) for x in group), 4), "render": round(mean(float(x["render_faithfulness"]) for x in group), 4), "feedback": round(mean(float(x["feedback_uptake"]) for x in group), 4)})
    return detailed, overall


def write_analysis(name: str, answer_sets: dict[str, dict[str, list[dict[str, Any]]]], process_sets: dict[str, list[dict[str, Any]]]) -> None:
    folder = OUT / name
    detailed, overall, pooled = accuracy_tables(answer_sets)
    full_answers = {model: settings["full"] for model, settings in answer_sets.items()}
    process_detail, process_overall = process_tables(process_sets, full_answers)
    write_csv(folder / "accuracy_by_model_setting_category.csv", detailed)
    write_csv(folder / "accuracy_by_model_setting_overall.csv", overall)
    write_csv(folder / "accuracy_by_setting_category_all_models.csv", pooled)
    write_csv(folder / "process_by_model_answer_category.csv", process_detail)
    write_csv(folder / "process_by_model_category.csv", process_overall)
    (folder / "summary.json").write_text(json.dumps({"split": name, "created_at": datetime.now().isoformat(timespec="seconds"), "answer_rows": sum(len(rows) for settings in answer_sets.values() for rows in settings.values()), "process_rows": sum(len(rows) for rows in process_sets.values()), "models": list(answer_sets), "settings": list(SETTINGS)}, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    old_answers: dict[str, dict[str, list[dict[str, Any]]]] = {}
    new_answers: dict[str, dict[str, list[dict[str, Any]]]] = {}
    old_process: dict[str, list[dict[str, Any]]] = {}
    new_process: dict[str, list[dict[str, Any]]] = {}
    sources: dict[str, dict[str, str]] = defaultdict(dict)
    for model, tag in MODELS:
        full = ready_rows(full_answer_path(tag), 1200)
        old_keys = set(map_rows(ready_rows(old_answer_path(tag, "text_only"), 600)))
        new_keys = set(map_rows(ready_rows(latest_completed_answer(tag, "text_only"), 600)))
        if len(old_keys | new_keys) != 1200 or old_keys & new_keys:
            raise RuntimeError(f"{model}: old/new answer partitions are not disjoint 600-task complements")
        old_answers[model] = {}
        new_answers[model] = {}
        for setting in ("text_only", "no_render", "wrong_render"):
            old_answers[model][setting] = ready_rows(old_answer_path(tag, setting), 600)
            new_answers[model][setting] = ready_rows(latest_completed_answer(tag, setting), 600)
        old_answers[model]["full"] = [row for row in full if row["task_key"] in old_keys]
        new_answers[model]["full"] = [row for row in full if row["task_key"] in new_keys]
        old_process[model] = ready_rows(old_process_path(tag), 600)
        new_process[model] = ready_rows(new_process_path(tag), 600)
        sources[model] = {"old_process": str(old_process_path(tag).relative_to(ROOT)), "new_process": str(new_process_path(tag).relative_to(ROOT))}

    merged_answers: dict[str, dict[str, list[dict[str, Any]]]] = {}
    merged_process: dict[str, list[dict[str, Any]]] = {}
    for model, _ in MODELS:
        merged_answers[model] = {setting: old_answers[model][setting] + new_answers[model][setting] for setting in SETTINGS}
        merged_process[model] = old_process[model] + new_process[model]
        for setting, rows in merged_answers[model].items():
            if len(map_rows(rows)) != 1200:
                raise RuntimeError(f"{model}/{setting}: merged result is not 1200 unique tasks")
        if len({row["task_key"] for row in merged_process[model]}) != 1200:
            raise RuntimeError(f"{model}: merged process result is not 1200 unique tasks")

    OUT.mkdir(parents=True, exist_ok=True)
    write_analysis("old_600", old_answers, old_process)
    write_analysis("new_600", new_answers, new_process)
    write_analysis("merged_1200", merged_answers, merged_process)
    (OUT / "README.md").write_text("# Split and merged analysis\n\n- `old_600`: historical evaluated IDs.\n- `new_600`: their disjoint 600-task complement.\n- `merged_1200`: exact task-key union of the two splits.\n", encoding="utf-8")
    (OUT / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
