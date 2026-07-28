import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "outputs" / "final_tracking"


MODEL_ALIASES = {
    "gemini-3.5-flash:stable": "gemini-3.5-flash",
}


SETTING_CONFIG = {
    "full": {
        "target": 1200,
        "run_setting": "vaot_full",
        "final_setting": "full",
        "require_render": True,
        "reusable_manifest": None,
        "newtask_roots": [
            "newtasks/final1200_{safe_model}_vaot_full_floor",
            "newtasks/final1154_{safe_model}_vaot_full_floor",
            "newtasks/final1154_{safe_model}_vaot_full",
        ],
        "subdir_templates": [
            "banana_{safe_model}_vaot_full",
            "banana_{model}_vaot_full",
        ],
        "reused_setting_dirs": [],
    },
    "text_only": {
        "target": 600,
        "run_setting": "text_cot",
        "final_setting": "text_only",
        "require_render": False,
        "reusable_manifest": "reusable_text_only_manifest.csv",
        "newtask_roots": [
            "newtasks/final1200_{safe_model}_text_cot",
            "newtasks/final600_{safe_model}_text_cot",
        ],
        "subdir_templates": [
            "banana_{safe_model}_text_cot",
            "banana_{model}_text_cot",
        ],
        "reused_setting_dirs": ["text_only"],
    },
    "no_render": {
        "target": 600,
        "run_setting": "vaot_no_render",
        "final_setting": "no_render",
        "require_render": False,
        "reusable_manifest": None,
        "newtask_roots": [
            "newtasks/final1200_{safe_model}_vaot_no_render",
            "newtasks/final600_{safe_model}_vaot_no_render",
        ],
        "subdir_templates": [
            "banana_{safe_model}_vaot_no_render",
            "banana_{model}_vaot_no_render",
        ],
        "reused_setting_dirs": ["no_render", "vaot_no_render"],
    },
    "wrong_render": {
        "target": 600,
        "run_setting": "vaot_wrong_render",
        "final_setting": "wrong_render",
        "require_render": True,
        "reusable_manifest": "reusable_valid_wrong_render_step1_manifest.csv",
        "newtask_roots": [
            "newtasks/final1200_{safe_model}_vaot_wrong_render_floor",
            "newtasks/final1200_{safe_model}_vaot_wrong_render",
            "newtasks/final600_{safe_model}_vaot_wrong_render_floor",
            "newtasks/final600_{safe_model}_vaot_wrong_render",
        ],
        "subdir_templates": [
            "banana_{safe_model}_vaot_wrong_render",
            "banana_{model}_vaot_wrong_render",
        ],
        "reused_setting_dirs": ["valid_wrong_render_step1", "wrong_render", "vaot_wrong_render"],
    },
}


def safe_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model).replace(":", "-")


def key_from_row(row: dict) -> tuple[str, str]:
    rel = (row.get("relative_source_dir") or "").replace("\\", "/")
    if not rel and row.get("path"):
        p = Path(row["path"].replace("\\", "/"))
        parts = list(p.parts)
        marker = ["annotation", "dataset", "data"]
        for i in range(0, len(parts) - len(marker) + 1):
            if parts[i : i + len(marker)] == marker:
                rel = "/".join(parts[i + len(marker) : -1])
                break
        if not rel and p.name == "data.json":
            rel = "/".join(p.parts[:-1])
    if not rel:
        rel = (row.get("source") or "").replace("\\", "/")
    sample_id = str(row.get("id", row.get("sample_id", row.get("index", ""))))
    return rel, sample_id


def load_manifest(setting: str) -> list[dict]:
    if setting == "full":
        path = ROOT / "json" / "tasks_see2thinkbench_1200task_available.json"
        rows = json.load(open(path, encoding="utf-8"))
        if len(rows) != SETTING_CONFIG[setting]["target"]:
            raise RuntimeError(
                f"Expected {SETTING_CONFIG[setting]['target']} rows in {path}, got {len(rows)}"
            )
        return rows
    path = TRACKING / "see2thinkbench_600_manifest.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 600:
        raise RuntimeError(f"Expected 600 rows in {path}, got {len(rows)}")
    return rows


def has_render(path: Path) -> bool:
    if not path.exists():
        return False
    for item in path.glob("p*"):
        if item.name == "p0.png":
            continue
        if item.suffix.lower() in {".png", ".jpg", ".jpeg"} and item.stat().st_size > 0:
            return True
    return False


def valid_result_dir(path: Path, require_render: bool) -> bool:
    steps = path / "steps.md"
    if not (steps.exists() and steps.stat().st_size > 0):
        return False
    return (not require_render) or has_render(path)


def load_reusable_index(manifest_name: str | None) -> dict[tuple[str, str, str], list[dict]]:
    index: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    if not manifest_name:
        return index
    path = TRACKING / manifest_name
    if not path.exists():
        return index
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            model = row["model"]
            rel = row["relative_source_dir"].replace("\\", "/")
            sample_id = str(row["sample_id"])
            index[(model, rel, sample_id)].append(row)
    return index


def candidate_new_dirs(model: str, rel: str, sample_id: str, cfg: dict) -> list[Path]:
    safe = safe_model(model)
    candidates = []
    for root_tpl in cfg["newtask_roots"]:
        root = ROOT / root_tpl.format(model=model, safe_model=safe)
        nested_root = root / root.name
        for sub_tpl in cfg["subdir_templates"]:
            subdir = sub_tpl.format(model=model, safe_model=safe)
            candidates.append(root / Path(*rel.split("/")) / subdir / sample_id)
            candidates.append(nested_root / Path(*rel.split("/")) / subdir / sample_id)
    return candidates


def candidate_reused_dirs(model: str, rel: str, sample_id: str, cfg: dict) -> list[Path]:
    safe = safe_model(model)
    candidates = []
    for setting_dir in cfg["reused_setting_dirs"]:
        for model_dir in {safe, model}:
            base = ROOT / "newtasks_reused" / model_dir / setting_dir / Path(*rel.split("/")) / sample_id
            candidates.append(base)
            candidates.append(base / sample_id)
    return candidates


def find_valid_source(model: str, rel: str, sample_id: str, cfg: dict) -> tuple[Path | None, str]:
    for path in candidate_new_dirs(model, rel, sample_id, cfg):
        if valid_result_dir(path, cfg["require_render"]):
            return path, "newtasks"
    for path in candidate_reused_dirs(model, rel, sample_id, cfg):
        if valid_result_dir(path, cfg["require_render"]):
            return path, "newtasks_reused"
    return None, "missing"


def copy_result(src: Path, dst: Path, overwrite: bool) -> None:
    if dst.exists():
        if overwrite:
            shutil.rmtree(dst)
        else:
            return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def assemble_model_setting(model: str, setting: str, final_rows: list[dict], overwrite: bool) -> dict:
    cfg = SETTING_CONFIG[setting]
    final_setting = cfg["final_setting"]
    out_root = ROOT / "final_results" / final_setting / safe_model(model)
    manifest_rows = []
    missing_rows = []
    counts = defaultdict(int)

    # Reusable index is kept for reporting: actual files must already be in newtasks_reused.
    reusable_index = load_reusable_index(cfg["reusable_manifest"])
    final_keys = {key_from_row(row) for row in final_rows}

    reusable_in_final = sum(
        1
        for (m, rel, sid), rows in reusable_index.items()
        if m == model and (rel, sid) in final_keys
    )

    for order, row in enumerate(final_rows):
        rel, sample_id = key_from_row(row)
        src, source_kind = find_valid_source(model, rel, sample_id, cfg)
        dst = out_root / Path(*rel.split("/")) / sample_id
        base = {
            "order": order,
            "model": model,
            "setting": final_setting,
            "relative_source_dir": rel,
            "sample_id": sample_id,
            "target_dir": str(dst.relative_to(ROOT)),
        }
        if src is None:
            missing = dict(base)
            missing["status"] = "missing"
            missing_rows.append(missing)
            continue

        copy_result(src, dst, overwrite=overwrite)
        counts[source_kind] += 1
        result = dict(base)
        result.update(
            {
                "status": "ok",
                "source_kind": source_kind,
                "source_dir": str(src.relative_to(ROOT)),
                "has_render": has_render(dst),
            }
        )
        manifest_rows.append(result)

    manifest_path = out_root / "_manifest.csv"
    missing_path = out_root / "_missing.csv"
    summary_path = out_root / "_summary.json"
    out_root.mkdir(parents=True, exist_ok=True)
    write_csv(manifest_path, manifest_rows)
    write_csv(missing_path, missing_rows)
    summary = {
        "model": model,
        "setting": final_setting,
        "target_total": cfg["target"],
        "valid": len(manifest_rows),
        "missing": len(missing_rows),
        "copied_from_newtasks": counts["newtasks"],
        "copied_from_reused": counts["newtasks_reused"],
        "reusable_rows_in_final_manifest": reusable_in_final,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "missing_file": str(missing_path.relative_to(ROOT)),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for row in rows for k in row.keys()})
    if not fieldnames:
        fieldnames = ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=[
        "gpt-5.5",
        "o3",
        "gemini-3.5-flash:stable",
        "qwen3-vl-8b-thinking",
        "qwen3-vl-32b-thinking",
    ])
    parser.add_argument("--settings", nargs="+", default=["full", "text_only", "no_render", "wrong_render"], choices=list(SETTING_CONFIG))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summaries = []
    for model in args.models:
        for setting in args.settings:
            final_rows = load_manifest(setting)
            print(f"ASSEMBLE model={model} setting={setting}")
            summary = assemble_model_setting(model, setting, final_rows, overwrite=args.overwrite)
            summaries.append(summary)
            print(
                f"  valid={summary['valid']}/{summary['target_total']} "
                f"missing={summary['missing']} new={summary['copied_from_newtasks']} reused={summary['copied_from_reused']}"
            )

    out_dir = ROOT / "outputs" / "final_tracking"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "assembled_final_results_summary.csv", summaries)
    (out_dir / "assembled_final_results_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(out_dir / "assembled_final_results_summary.csv")


if __name__ == "__main__":
    main()
