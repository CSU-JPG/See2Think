"""Assemble the two 600-task batches into non-destructive 1,200-task result trees.

The source runs live in ``newtasks`` / ``newtasks_reused``.  This script creates
``final_results_1200`` without touching the existing 600-task ``final_results``
trees.  Files are hard-linked where possible, so the assembled view does not
duplicate the rendered images on the same NTFS volume.
"""

import argparse
import csv
import importlib.util
import json
import os
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "final_results_1200"
TRACKING = ROOT / "outputs" / "final_tracking"
MODELS = ["gpt-5.5", "o3", "gemini-3.5-flash:stable", "qwen3-vl-32b-instruct"]
SETTINGS = ["text_only", "no_render", "wrong_render", "full"]


def load_assembler():
    path = ROOT / "scripts" / "assemble_final_results.py"
    spec = importlib.util.spec_from_file_location("assembler", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


A = load_assembler()


def hardlink_or_copy(src: str, dst: str) -> str:
    try:
        os.link(src, dst)
        return dst
    except OSError:
        return shutil.copy2(src, dst)


def copy_result(src: Path, dst: Path, overwrite: bool) -> None:
    if dst.exists():
        if not overwrite:
            return
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, copy_function=hardlink_or_copy)


def has_steps(path: Path) -> bool:
    steps = path / "steps.md"
    return steps.exists() and steps.stat().st_size > 0


def full_source(model: str, rel: str, sample_id: str) -> Path | None:
    safe = A.safe_model(model)
    base = (
        ROOT
        / "newtasks"
        / f"final1200_{safe}_vaot_full_floor"
        / Path(*rel.split("/"))
    )
    candidates = [
        base / sample_id,
        base / f"banana_{safe}_vaot_full" / sample_id,
        ROOT / "final_results" / "full" / safe / Path(*rel.split("/")) / sample_id,
    ]
    return next((path for path in candidates if A.valid_result_dir(path, True)), None)


def source_for(model: str, setting: str, rel: str, sample_id: str):
    if setting == "full":
        src = full_source(model, rel, sample_id)
        return src, "full_1200", "ok" if src else "missing"

    cfg = A.SETTING_CONFIG[setting]
    # Prefer outputs that have all artifacts required by the setting.
    src, kind = A.find_valid_source(model, rel, sample_id, cfg)
    if src:
        return src, kind, "ok"

    # For WrongRender, retain a completed textual answer even if its p1+ image
    # was not written.  The manifest keeps these explicitly flagged so process
    # metrics can exclude them while answer accuracy can still include them.
    if setting == "wrong_render":
        for path in A.candidate_new_dirs(model, rel, sample_id, cfg):
            if has_steps(path):
                return path, "newtasks", "missing_render"
        for path in A.candidate_reused_dirs(model, rel, sample_id, cfg):
            if has_steps(path):
                return path, "newtasks_reused", "missing_render"
    return None, "missing", "missing"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row}) or ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    rows = json.loads((ROOT / "json" / "tasks_see2thinkbench_1200task_available.json").read_text(encoding="utf-8"))
    if len(rows) != 1200:
        raise RuntimeError(f"Expected 1200 canonical tasks, got {len(rows)}")

    summaries = []
    for setting in SETTINGS:
        for model in MODELS:
            safe = A.safe_model(model)
            root = OUT_ROOT / setting / safe
            manifest, missing = [], []
            source_counts, status_counts = Counter(), Counter()
            for order, row in enumerate(rows):
                rel, sample_id = A.key_from_row(row)
                src, source_kind, status = source_for(model, setting, rel, sample_id)
                dst = root / Path(*rel.split("/")) / sample_id
                item = {
                    "order": order,
                    "model": model,
                    "setting": setting,
                    "relative_source_dir": rel,
                    "sample_id": sample_id,
                    "status": status,
                    "source_kind": source_kind,
                    "target_dir": str(dst.relative_to(ROOT)),
                }
                if src is None:
                    missing.append(item)
                    status_counts[status] += 1
                    continue
                copy_result(src, dst, args.overwrite)
                item.update({
                    "source_dir": str(src.relative_to(ROOT)),
                    "has_render": A.has_render(src),
                })
                manifest.append(item)
                source_counts[source_kind] += 1
                status_counts[status] += 1

            root.mkdir(parents=True, exist_ok=True)
            write_csv(root / "_manifest.csv", manifest)
            write_csv(root / "_missing.csv", missing)
            summary = {
                "model": model,
                "setting": setting,
                "target": 1200,
                "assembled": len(manifest),
                "missing": len(missing),
                "source_counts": dict(source_counts),
                "status_counts": dict(status_counts),
            }
            (root / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False))

    TRACKING.mkdir(parents=True, exist_ok=True)
    summary_path = TRACKING / "assembled_all_1200_summary.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {summary_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()


