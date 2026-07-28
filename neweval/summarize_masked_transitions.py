#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def transition(before: bool, after: bool) -> str:
    if before and after:
        return "right_to_right"
    if before and not after:
        return "right_to_wrong"
    if not before and after:
        return "wrong_to_right"
    return "wrong_to_wrong"


def summarize(rows: list[dict[str, Any]], before_key: str, after_key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "right_to_right": [],
        "right_to_wrong": [],
        "wrong_to_right": [],
        "wrong_to_wrong": [],
    }
    for row in rows:
        before = as_bool(row[before_key])
        after = as_bool(row[after_key])
        label = transition(before, after)
        buckets[label].append(row)
    return {
        "count": len(rows),
        "transitions": {
            label: {
                "count": len(items),
                "rate": round(len(items) / len(rows), 4) if rows else None,
            }
            for label, items in buckets.items()
        },
        "by_family": summarize_by(rows, "family", before_key, after_key),
        "by_model": summarize_by(rows, "model", before_key, after_key),
    }


def summarize_by(rows: list[dict[str, Any]], group_key: str, before_key: str, after_key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for group in sorted({row[group_key] for row in rows}):
        group_rows = [row for row in rows if row[group_key] == group]
        counts = {"right_to_right": 0, "right_to_wrong": 0, "wrong_to_right": 0, "wrong_to_wrong": 0}
        for row in group_rows:
            counts[transition(as_bool(row[before_key]), as_bool(row[after_key]))] += 1
        out[group] = {"count": len(group_rows), **counts}
    return out


def write_transition_csv(path: Path, rows: list[dict[str, Any]], before_key: str, after_key: str, setting: str) -> None:
    fields = ["setting", "transition", "family", "model", "task_key", "sample_id", before_key, after_key]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {
                "setting": setting,
                "transition": transition(as_bool(row[before_key]), as_bool(row[after_key])),
                "family": row["family"],
                "model": row["model"],
                "task_key": row["task_key"],
                "sample_id": row["sample_id"],
                before_key: row[before_key],
                after_key: row[after_key],
            }
            writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize unmasked->masked answer transition directions.")
    parser.add_argument("--comparison-csv", default="neweval/results/masked_action_audit120_comparison/comparison_rows.csv")
    parser.add_argument("--output-dir", default="neweval/results/masked_action_audit120_comparison")
    args = parser.parse_args()

    rows = read_rows(Path(args.comparison_csv))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "full": summarize(rows, "unmasked_full_correct", "masked_full_correct"),
        "wrong_render": summarize(rows, "unmasked_wrong_render_correct", "masked_wrong_render_correct"),
    }
    (out_dir / "transition_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_transition_csv(
        out_dir / "full_transitions.csv",
        rows,
        "unmasked_full_correct",
        "masked_full_correct",
        "full",
    )
    write_transition_csv(
        out_dir / "wrong_render_transitions.csv",
        rows,
        "unmasked_wrong_render_correct",
        "masked_wrong_render_correct",
        "wrong_render",
    )
    print(json.dumps({k: v["transitions"] for k, v in summary.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
