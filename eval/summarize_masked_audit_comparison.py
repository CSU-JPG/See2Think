#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Any


FULL_RESULT_BY_MODEL = {
    "gpt-5.5": "answer_gpt55_final1200_vaot_full",
    "o3": "answer_o3_final1200_vaot_full",
    "gemini-3.5-flash": "answer_gemini35flash_final1200_vaot_full",
}

WRONG_RESULT_BY_MODEL = {
    "gpt-5.5": "answer_gpt55_wrong_render_600",
    "o3": "answer_o3_wrong_render_600",
    "gemini-3.5-flash": "answer_gemini35flash_wrong_render_600",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_result_map(results_root: Path, result_by_model: dict[str, str]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for model, run_name in result_by_model.items():
        for row in load_jsonl(results_root / run_name / "answer_judge.jsonl"):
            out[(model, row["task_key"])] = row
    return out


def accuracy(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    total = len(rows)
    correct = sum(1 for row in rows if row.get(key) is True)
    return {
        "count": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
    }


def grouped(rows: list[dict[str, Any]], group_key: str, metric_key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    groups = sorted({str(row.get(group_key, "")) for row in rows})
    for group in groups:
        result[group] = accuracy([row for row in rows if str(row.get(group_key, "")) == group], metric_key)
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "family",
        "model",
        "task_key",
        "sample_id",
        "unmasked_full_correct",
        "masked_full_correct",
        "full_changed",
        "unmasked_wrong_render_correct",
        "masked_wrong_render_correct",
        "wrong_render_changed",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare unmasked vs masked-action ACC on the 120 WrongRender audit samples.")
    parser.add_argument("--audit-csv", default="outputs/human_audit/wrong_render_120/wrong_render_audit_120.csv")
    parser.add_argument("--results-root", default="eval/results")
    parser.add_argument("--output-dir", default="eval/results/masked_action_audit120_comparison")
    args = parser.parse_args()

    results_root = Path(args.results_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    unmasked_full = load_result_map(results_root, FULL_RESULT_BY_MODEL)
    unmasked_wrong = load_result_map(results_root, WRONG_RESULT_BY_MODEL)
    masked_full = {(row["model"], row["task_key"]): row for row in load_jsonl(results_root / "answer_masked_action_audit120_full" / "answer_judge.jsonl")}
    masked_wrong = {(row["model"], row["task_key"]): row for row in load_jsonl(results_root / "answer_masked_action_audit120_wrong_render" / "answer_judge.jsonl")}

    comparison_rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    with Path(args.audit_csv).open("r", encoding="utf-8-sig", newline="") as f:
        for audit_row in csv.DictReader(f):
            model = audit_row["model"]
            task_key = audit_row["task_key"]
            key = (model, task_key)
            sources = {
                "unmasked_full": unmasked_full.get(key),
                "masked_full": masked_full.get(key),
                "unmasked_wrong_render": unmasked_wrong.get(key),
                "masked_wrong_render": masked_wrong.get(key),
            }
            for name, row in sources.items():
                if row is None:
                    missing.append({"source": name, "model": model, "task_key": task_key})
            if any(row is None for row in sources.values()):
                continue
            assert sources["unmasked_full"] is not None
            assert sources["masked_full"] is not None
            assert sources["unmasked_wrong_render"] is not None
            assert sources["masked_wrong_render"] is not None
            row = {
                "family": audit_row["family"],
                "model": model,
                "task_key": task_key,
                "sample_id": int(audit_row["sample_id"]),
                "unmasked_full_correct": sources["unmasked_full"]["correct"],
                "masked_full_correct": sources["masked_full"]["correct"],
                "full_changed": sources["unmasked_full"]["correct"] != sources["masked_full"]["correct"],
                "unmasked_wrong_render_correct": sources["unmasked_wrong_render"]["correct"],
                "masked_wrong_render_correct": sources["masked_wrong_render"]["correct"],
                "wrong_render_changed": sources["unmasked_wrong_render"]["correct"] != sources["masked_wrong_render"]["correct"],
            }
            comparison_rows.append(row)

    metrics = [
        "unmasked_full_correct",
        "masked_full_correct",
        "unmasked_wrong_render_correct",
        "masked_wrong_render_correct",
    ]
    summary: dict[str, Any] = {
        "count": len(comparison_rows),
        "missing_count": len(missing),
        "overall": {metric: accuracy(comparison_rows, metric) for metric in metrics},
        "by_family": {metric: grouped(comparison_rows, "family", metric) for metric in metrics},
        "by_model": {metric: grouped(comparison_rows, "model", metric) for metric in metrics},
    }
    if comparison_rows:
        summary["deltas"] = {
            "masked_full_minus_unmasked_full": round(summary["overall"]["masked_full_correct"]["accuracy"] - summary["overall"]["unmasked_full_correct"]["accuracy"], 4),
            "masked_wrong_render_minus_unmasked_wrong_render": round(
                summary["overall"]["masked_wrong_render_correct"]["accuracy"] - summary["overall"]["unmasked_wrong_render_correct"]["accuracy"],
                4,
            ),
            "unmasked_wrong_render_minus_unmasked_full": round(
                summary["overall"]["unmasked_wrong_render_correct"]["accuracy"] - summary["overall"]["unmasked_full_correct"]["accuracy"],
                4,
            ),
            "masked_wrong_render_minus_masked_full": round(
                summary["overall"]["masked_wrong_render_correct"]["accuracy"] - summary["overall"]["masked_full_correct"]["accuracy"],
                4,
            ),
        }

    (out_dir / "comparison_rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in comparison_rows),
        encoding="utf-8",
    )
    write_csv(out_dir / "comparison_rows.csv", comparison_rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "missing.json").write_text(json.dumps(missing, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))
    print(f"wrote {out_dir}")
    if missing:
        print(f"missing={len(missing)}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
