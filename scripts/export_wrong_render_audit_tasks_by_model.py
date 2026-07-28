import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/human_audit/wrong_render_120/wrong_render_audit_120.csv"
OUT_DIR = ROOT / "json/run_tasks_wrong_render_audit_120"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_by_model: dict[str, list[dict]] = {}
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            model = row["model"]
            rel = row["relative_source_dir"].replace("\\", "/")
            rows_by_model.setdefault(model, []).append(
                {
                    "path": f"annotation/dataset/data/{rel}/data.json",
                    "id": int(row["sample_id"]),
                    "relative_source_dir": rel,
                    "source_audit_file": str(INPUT.relative_to(ROOT)),
                    "audit_family": row["family"],
                    "audit_best_model": model,
                }
            )
    index = []
    for model, rows in sorted(rows_by_model.items()):
        rows.sort(key=lambda r: (r["relative_source_dir"], r["id"]))
        safe = model.replace(":", "-")
        out = OUT_DIR / f"{safe}__wrong_render_audit_120.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"model": model, "tasks": str(out.relative_to(ROOT)), "count": len(rows)})
        print(f"{model}: {len(rows)} -> {out}")
    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
