import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_1200 = ROOT / "json" / "tasks_see2thinkbench_1200task_available.json"
MATCHED_600 = ROOT / "outputs" / "final_tracking" / "see2thinkbench_600_manifest.csv"
OUT_DIR = ROOT / "json" / "run_tasks_remaining_600"


def key_from_json(row: dict) -> tuple[str, str]:
    rel = (row.get("relative_source_dir") or "").replace("\\", "/")
    if not rel:
        path = Path(str(row["path"]).replace("\\", "/"))
        marker = ("annotation", "dataset", "data")
        parts = path.parts
        for i in range(len(parts) - len(marker) + 1):
            if parts[i : i + len(marker)] == marker:
                rel = "/".join(parts[i + len(marker) : -1])
                break
        if not rel and path.name == "data.json":
            rel = "/".join(path.parts[:-1])
    sample_id = str(row.get("id", row.get("sample_id", row.get("index", ""))))
    return rel, sample_id


def key_from_csv(row: dict) -> tuple[str, str]:
    sample_id = row.get("sample_id", row.get("id", row.get("index", "")))
    return row["relative_source_dir"].replace("\\", "/"), str(sample_id)


def main() -> None:
    full = json.load(open(FULL_1200, encoding="utf-8"))
    with MATCHED_600.open("r", encoding="utf-8-sig", newline="") as f:
        matched = {key_from_csv(row) for row in csv.DictReader(f)}
    remaining = [row for row in full if key_from_json(row) not in matched]
    if len(remaining) != 600:
        raise RuntimeError(f"Expected 600 remaining tasks, got {len(remaining)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = OUT_DIR / "remaining_600.json"
    base.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")

    models = ["gpt-5.5", "o3", "gemini-3.5-flash"]
    settings = ["text_cot", "vaot_no_render", "vaot_wrong_render"]
    for model in models:
        for setting in settings:
            path = OUT_DIR / f"{model}__{setting}__remaining_600.json"
            path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {len(remaining)} tasks to {base.relative_to(ROOT)}")
    print(f"wrote per-model/per-setting task files under {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
