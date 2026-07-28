"""Generate browser data for the WrongRender human-audit frontend."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "outputs" / "human_audit" / "wrong_render_1200"
WEB = AUDIT / "web_annotation"


def url(value: str) -> str:
    return "/" + value.replace("\\", "/").lstrip("/")


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    with (AUDIT / "wrong_render_audit_tasks.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    items = []
    for row in rows:
        items.append({
            "audit_id": row["audit_id"], "model": row["model"], "family": row["family"],
            "task_key": row["task_key"], "sample_id": row["sample_id"],
            "action_step": row["action_step"], "action_type": row["action_type"],
            "full_family_accuracy": row["full_family_accuracy"], "action_json": row["action_json"],
            "original_image": url(row["original_image"]),
            "correct_render_image": url(row["correct_render_image"]),
            "wrong_render_image": url(row["wrong_render_image"]),
            "steps_md": url(row["steps_md"]),
        })
    (WEB / "audit_items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(items)} audit items to {WEB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
