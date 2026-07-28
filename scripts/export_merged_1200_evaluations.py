"""Export complete task-level 1,200-row evaluation results into merged_1200."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
OUT = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200" / "complete_evaluations"
MODELS = (("gpt-5.5", "gpt55"), ("o3", "o3"), ("gemini-3.5-flash", "gemini35flash"))
SETTINGS = ("text_only", "no_render", "full", "wrong_render")


def load_analysis_module():
    path = ROOT / "scripts" / "analyze_split_and_merged_1200.py"
    spec = importlib.util.spec_from_file_location("split_analysis", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


A = load_analysis_module()


def canonical_key(row: dict) -> str:
    path = row["path"].replace("\\", "/")
    prefix = "annotation/dataset/data/"
    if path.startswith(prefix):
        path = path[len(prefix):]
    if path.endswith("/data.json"):
        path = path[: -len("/data.json")]
    return f"{path}::{row['id']}"


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def merge_rows(old_rows: list[dict], new_rows: list[dict], canonical_order: list[str]) -> list[dict]:
    merged = {}
    for split, rows in (("old_600", old_rows), ("new_600", new_rows)):
        for row in rows:
            item = dict(row)
            item["evaluation_split"] = split
            item["paper_category"] = A.paper_category(item)
            key = str(item["task_key"])
            if key in merged:
                raise RuntimeError(f"Duplicate task key: {key}")
            merged[key] = item
    if set(merged) != set(canonical_order):
        raise RuntimeError(f"Expected canonical 1200 IDs; got {len(merged)} unique rows")
    return [merged[key] for key in canonical_order]


def main() -> None:
    tasks = json.loads((ROOT / "json" / "tasks_see2thinkbench_1200task_available.json").read_text(encoding="utf-8"))
    order = [canonical_key(row) for row in tasks]
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "task_count": len(order),
        "acc_evaluation_all_settings": {},
        "process_metrics_full_only": {},
    }

    for model, tag in MODELS:
        answer_manifest = {}
        old_text = A.ready_rows(A.old_answer_path(tag, "text_only"), 600)
        old_keys = set(A.map_rows(old_text))
        for setting in SETTINGS:
            if setting == "full":
                rows = A.ready_rows(A.full_answer_path(tag), 1200)
                for row in rows:
                    row["evaluation_split"] = "direct_full_1200"
                    row["paper_category"] = A.paper_category(row)
            else:
                old_rows = A.ready_rows(A.old_answer_path(tag, setting), 600)
                new_rows = A.ready_rows(A.latest_completed_answer(tag, setting), 600)
                rows = merge_rows(old_rows, new_rows, order)
            if len(rows) != 1200:
                raise RuntimeError(f"{model}/{setting}: export is not 1200 rows")
            path = OUT / f"answer_{tag}_{setting}_1200.jsonl"
            dump_jsonl(path, rows)
            answer_manifest[setting] = {"path": path.name, "rows": len(rows)}

        old_process = A.ready_rows(A.old_process_path(tag), 600)
        new_process = A.ready_rows(A.new_process_path(tag), 600)
        process_rows = merge_rows(old_process, new_process, order)
        path = OUT / f"process_eval_{tag}_full_1200.jsonl"
        dump_jsonl(path, process_rows)
        manifest["acc_evaluation_all_settings"][model] = answer_manifest
        manifest["process_metrics_full_only"][model] = {"path": path.name, "rows": len(process_rows)}

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Complete merged 1,200-task evaluations\n\n"
        "Each `answer_*` JSONL is the complete answer-accuracy evaluation for one model and one setting, with one row per canonical benchmark task in task order. "
        "There are 12 such files: 3 models × (CoT, NoRender, Full, WrongRender). "
        "Non-Full settings are exact old/new 600 task-key unions. Full answer results were already judged directly on all 1,200 tasks. "
        "The three `process_eval_*_full_1200.jsonl` files are a separate Action/Render/Feedback process-metric evaluation, which is defined here only for VAoT-Full.\n",
        encoding="utf-8",
    )
    print(OUT)


if __name__ == "__main__":
    main()
