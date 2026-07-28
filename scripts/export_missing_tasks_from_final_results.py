import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--setting", required=True, choices=["full", "text_only", "no_render", "wrong_render"])
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    safe_model = args.model.replace(":", "-")
    missing_csv = ROOT / "final_results" / args.setting / safe_model / "_missing.csv"
    if not missing_csv.exists():
        raise SystemExit(f"missing csv not found: {missing_csv}")

    rows = []
    with missing_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rel = row["relative_source_dir"].replace("\\", "/")
            sample_id = int(row["sample_id"])
            rows.append(
                {
                    "path": f"annotation/dataset/data/{rel}/data.json",
                    "id": sample_id,
                    "relative_source_dir": rel,
                    "source_missing_file": str(missing_csv.relative_to(ROOT)),
                }
            )

    out_dir = ROOT / "json" / "run_tasks_need_600_retry"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_model}__{args.setting}__missing_final_results.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
