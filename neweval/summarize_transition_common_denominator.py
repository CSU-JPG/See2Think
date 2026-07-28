#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


MODELS = {
    "gpt-5.5": {
        "safe": "gpt55",
        "full": "answer_gpt55_final600subset_vaot_full",
        "no_render": "answer_gpt55_no_render_600",
        "wrong_render": "answer_gpt55_wrong_render_600",
        "metric": "key_step_metric_gpt55_final600_vaot_full",
        "answer_change": "answer_change_gpt55_full_vs_wrongrender",
    },
    "o3": {
        "safe": "o3",
        "full": "answer_o3_final600subset_vaot_full",
        "no_render": "answer_o3_no_render_600",
        "wrong_render": "answer_o3_wrong_render_600",
        "metric": "key_step_metric_o3_final600_vaot_full",
        "answer_change": "answer_change_o3_full_vs_wrongrender",
    },
    "gemini-3.5-flash": {
        "safe": "gemini35flash",
        "full": "answer_gemini35flash_final600subset_vaot_full",
        "no_render": "answer_gemini35flash_no_render_600",
        "wrong_render": "answer_gemini35flash_wrong_render_600",
        "metric": "key_step_metric_gemini35flash_final600_vaot_full",
        "answer_change": "answer_change_gemini35flash_full_vs_wrongrender",
    },
}


TASK_FAMILY = {
    "math": ("2D", "Geo"),
    "emma/math": ("2D", "Puzzle"),
    "emma/physics": ("2D", "Phys"),
    "emma/chemistry": ("2D", "Chem"),
    "m3cot/test1": ("2D", "Sci"),
    "prism": ("2D", "Prism"),
    "clevr_math/val": ("3D", "CLEVR"),
    "super_clevr": ("3D", "S-CLEVR"),
    "VLABench": ("Real-world", "VLA"),
    "droid": ("Real-world", "DROID"),
    "m3cot/test0": ("Real-world", "Comm."),
    "intphy2": ("Real-world", "IntPhys"),
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def float_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def rate(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def load_answer_map(results_root: Path, run_name: str) -> dict[str, dict[str, str]]:
    rows = load_csv(results_root / run_name / "answer_judge.csv")
    return {row["task_key"]: row for row in rows if row.get("status") == "ok"}


def load_metric_map(results_root: Path, run_name: str) -> dict[str, dict[str, str]]:
    rows = load_csv(results_root / run_name / "key_step_metric_judge.csv")
    return {row["task_key"]: row for row in rows if row.get("status") == "ok"}


def load_change_map(results_root: Path, run_name: str) -> dict[str, dict[str, str]]:
    rows = load_csv(results_root / run_name / "answer_change_judge.csv")
    return {row["task_key"]: row for row in rows if row.get("status") == "ok"}


def build_master(results_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    master: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for model, cfg in MODELS.items():
        full = load_answer_map(results_root, cfg["full"])
        no_render = load_answer_map(results_root, cfg["no_render"])
        wrong = load_answer_map(results_root, cfg["wrong_render"])
        metric = load_metric_map(results_root, cfg["metric"])
        change = load_change_map(results_root, cfg["answer_change"])
        all_keys = sorted(set(full) | set(no_render) | set(wrong) | set(metric))
        for key in all_keys:
            sources = {
                "full": key in full,
                "no_render": key in no_render,
                "wrong_render": key in wrong,
                "metric": key in metric,
                "answer_change": key in change,
            }
            if not all(sources.values()):
                missing.append({"model": model, "task_key": key, **sources})
                continue
            rel = full[key].get("relative_source_dir") or metric[key].get("relative_source_dir")
            task_group, task_family = TASK_FAMILY.get(rel, ("UNKNOWN", rel))
            row = {
                "model": model,
                "task_key": key,
                "sample_id": full[key].get("sample_id"),
                "relative_source_dir": rel,
                "task_group": task_group,
                "task_family": task_family,
                "no_render_answer": no_render[key].get("final_answer", ""),
                "no_render_correct": bool_value(no_render[key].get("correct")),
                "full_answer": full[key].get("final_answer", ""),
                "full_correct": bool_value(full[key].get("correct")),
                "wrongrender_answer": wrong[key].get("final_answer", ""),
                "wrongrender_correct": bool_value(wrong[key].get("correct")),
                "answer_changed": bool_value(change[key].get("answer_changed")),
                "answers_equivalent": bool_value(change[key].get("answers_equivalent")),
                "key_step_id": metric[key].get("key_step_id"),
                "action_relevance": float_value(metric[key].get("action_relevance")),
                "render_faithfulness": float_value(metric[key].get("render_faithfulness")),
                "feedback_uptake": float_value(metric[key].get("feedback_uptake")),
                "key_step_reason": metric[key].get("key_step_reason", ""),
                "action_relevance_reason": metric[key].get("action_relevance_reason", ""),
                "render_faithfulness_reason": metric[key].get("render_faithfulness_reason", ""),
                "feedback_uptake_reason": metric[key].get("feedback_uptake_reason", ""),
            }
            nr = row["no_render_correct"]
            fu = row["full_correct"]
            wr = row["wrongrender_correct"]
            if nr is False and fu is True:
                row["render_transition"] = "Render Benefit"
            elif nr is True and fu is False:
                row["render_transition"] = "Render Harm"
            elif nr is True and fu is True:
                row["render_transition"] = "Both Correct"
            elif nr is False and fu is False:
                row["render_transition"] = "Both Incorrect"
            else:
                row["render_transition"] = "UNKNOWN"
            if fu is True and wr is False:
                row["corruption_transition"] = "Corruption Harm"
            elif fu is False and wr is True:
                row["corruption_transition"] = "Corruption Correction"
            elif fu is True and wr is True:
                row["corruption_transition"] = "Both Correct"
            elif fu is False and wr is False:
                row["corruption_transition"] = "Both Incorrect"
            else:
                row["corruption_transition"] = "UNKNOWN"
            master.append(row)
    return master, missing


def summarize_render(rows: list[dict[str, Any]], group_name: str, model: str, task_group: str, rf: str) -> dict[str, Any]:
    n = len(rows)
    benefit = sum(1 for r in rows if r["render_transition"] == "Render Benefit")
    harm = sum(1 for r in rows if r["render_transition"] == "Render Harm")
    both_correct = sum(1 for r in rows if r["render_transition"] == "Both Correct")
    both_incorrect = sum(1 for r in rows if r["render_transition"] == "Both Incorrect")
    no_render_correct = sum(1 for r in rows if r["no_render_correct"] is True)
    full_correct = sum(1 for r in rows if r["full_correct"] is True)
    return {
        "scope": group_name,
        "model": model,
        "task_group": task_group,
        "render_faithfulness": rf,
        "n": n,
        "no_render_correct": no_render_correct,
        "full_correct": full_correct,
        "no_render_acc": rate(no_render_correct, n),
        "full_acc": rate(full_correct, n),
        "render_benefit_count": benefit,
        "render_harm_count": harm,
        "both_correct_count": both_correct,
        "both_incorrect_count": both_incorrect,
        "render_benefit_share": rate(benefit, n),
        "render_harm_share": rate(harm, n),
        "delta_acc_share": round((benefit - harm) / n, 6) if n else None,
    }


def summarize_corruption(rows: list[dict[str, Any]], group_name: str, model: str, task_group: str, fu: str) -> dict[str, Any]:
    n = len(rows)
    harm = sum(1 for r in rows if r["corruption_transition"] == "Corruption Harm")
    correction = sum(1 for r in rows if r["corruption_transition"] == "Corruption Correction")
    both_correct = sum(1 for r in rows if r["corruption_transition"] == "Both Correct")
    both_incorrect = sum(1 for r in rows if r["corruption_transition"] == "Both Incorrect")
    full_correct = sum(1 for r in rows if r["full_correct"] is True)
    wrong_correct = sum(1 for r in rows if r["wrongrender_correct"] is True)
    answer_changed = sum(1 for r in rows if r["answer_changed"] is True)
    return {
        "scope": group_name,
        "model": model,
        "task_group": task_group,
        "feedback_uptake": fu,
        "n": n,
        "full_correct": full_correct,
        "wrongrender_correct": wrong_correct,
        "full_acc": rate(full_correct, n),
        "wrongrender_acc": rate(wrong_correct, n),
        "corruption_harm_count": harm,
        "corruption_correction_count": correction,
        "both_correct_count": both_correct,
        "both_incorrect_count": both_incorrect,
        "corruption_harm_share": rate(harm, n),
        "corruption_correction_share": rate(correction, n),
        "delta_acc_wrongrender_minus_full": round((correction - harm) / n, 6) if n else None,
        "answer_changed": answer_changed,
        "answer_change_rate": rate(answer_changed, n),
    }


def bucket_rows(master: list[dict[str, Any]], metric: str, model: str | None, task_group: str | None, value: float | None) -> list[dict[str, Any]]:
    out = []
    for row in master:
        if model is not None and row["model"] != model:
            continue
        if task_group is not None and row["task_group"] != task_group:
            continue
        if value is not None and row.get(metric) != value:
            continue
        out.append(row)
    return out


def make_summaries(master: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    render_rows: list[dict[str, Any]] = []
    corruption_rows: list[dict[str, Any]] = []
    models = [None, *MODELS.keys()]
    groups = [None, "2D", "3D", "Real-world"]
    rf_values: list[float | None] = [None, 0.0, 0.5, 1.0]
    fu_values: list[float | None] = [None, 0.0, 0.5, 1.0]
    for model in models:
        for group in groups:
            for rf in rf_values:
                rows = bucket_rows(master, "render_faithfulness", model, group, rf)
                if rows:
                    render_rows.append(
                        summarize_render(rows, "all" if rf is None else "by_rf", model or "ALL", group or "Overall", "ALL" if rf is None else str(rf))
                    )
            for fu in fu_values:
                rows = bucket_rows(master, "feedback_uptake", model, group, fu)
                if rows:
                    corruption_rows.append(
                        summarize_corruption(rows, "all" if fu is None else "by_fu", model or "ALL", group or "Overall", "ALL" if fu is None else str(fu))
                    )
    return render_rows, corruption_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize transition shares with common denominators.")
    parser.add_argument("--results-root", default="neweval/results")
    parser.add_argument("--out-dir", default="neweval/results/transition_common_denominator_600")
    args = parser.parse_args()

    results_root = Path(args.results_root)
    out_dir = Path(args.out_dir)
    master, missing = build_master(results_root)
    render_rows, corruption_rows = make_summaries(master)

    write_csv(out_dir / "master_transition_table.csv", master)
    write_csv(out_dir / "missing_rows.csv", missing)
    write_csv(out_dir / "norender_full_by_rf_common_denominator.csv", render_rows)
    write_csv(out_dir / "full_wrongrender_by_fu_common_denominator.csv", corruption_rows)
    write_json(
        out_dir / "summary.json",
        {
            "master_rows": len(master),
            "missing_rows": len(missing),
            "expected_rows": 1800,
            "group_mapping": {k: {"task_group": v[0], "task_family": v[1]} for k, v in TASK_FAMILY.items()},
            "outputs": [
                "master_transition_table.csv",
                "missing_rows.csv",
                "norender_full_by_rf_common_denominator.csv",
                "full_wrongrender_by_fu_common_denominator.csv",
            ],
        },
    )
    print(f"master_rows={len(master)} missing_rows={len(missing)} out={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
