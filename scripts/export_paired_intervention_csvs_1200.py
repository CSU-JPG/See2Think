"""Export the two appendix paired-intervention CSVs on the final 1,200 tasks.

Task groups use the paper taxonomy: 2D (six families), 3D (two), Real (four).
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200"
INPUT = BASE / "complete_evaluations"
SEMANTIC = BASE / "semantic_answer_change_1200"
MODELS = (
    ("gpt-5.5", "gpt55", "gpt55_full_vs_wrongrender_1200"),
    ("o3", "o3", "o3_full_vs_wrongrender_1200"),
    ("gemini-3.5-flash", "gemini35flash", "gemini35flash_full_vs_wrongrender_1200"),
)
CATEGORIES = ("2D", "3D", "Real")
BINS = (0.0, 0.5, 1.0)


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mapping(rows: list[dict]) -> dict[str, dict]:
    return {str(row["task_key"]): row for row in rows}


def ratio(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def main() -> None:
    by_model: dict[str, list[dict]] = {}
    for model, tag, semantic_run in MODELS:
        no_render = mapping(load(INPUT / f"answer_{tag}_no_render_1200.jsonl"))
        full = mapping(load(INPUT / f"answer_{tag}_full_1200.jsonl"))
        wrong = mapping(load(INPUT / f"answer_{tag}_wrong_render_1200.jsonl"))
        process = load(INPUT / f"process_eval_{tag}_full_1200.jsonl")
        change = mapping(load(SEMANTIC / semantic_run / "answer_change_judge.jsonl"))
        if not (len(no_render) == len(full) == len(wrong) == len(process) == len(change) == 1200):
            raise RuntimeError(f"{model}: expected 1,200 aligned records")
        rows: list[dict] = []
        for item in process:
            if item.get("status") != "ok":
                continue
            key = str(item["task_key"])
            rows.append({
                "model": model,
                "task_group": str(item["paper_category"]),
                "rf": float(item["render_faithfulness"]),
                "fu": float(item["feedback_uptake"]),
                "no_correct": bool(no_render[key]["correct"]),
                "full_correct": bool(full[key]["correct"]),
                "wrong_correct": bool(wrong[key]["correct"]),
                "answer_changed": bool(change[key]["answer_changed"]),
            })
        by_model[model] = rows

    all_rows = [row for rows in by_model.values() for row in rows]
    rf_out: list[dict] = []
    fu_out: list[dict] = []
    for model, records in (("ALL", all_rows), *by_model.items()):
        for group in ("Overall", *CATEGORIES):
            category_rows = records if group == "Overall" else [r for r in records if r["task_group"] == group]
            for scope, field, bins in (("all", "rf", ("ALL",)), ("by_rf", "rf", BINS)):
                for value in bins:
                    selected = category_rows if value == "ALL" else [r for r in category_rows if r[field] == value]
                    n = len(selected)
                    no_correct = sum(r["no_correct"] for r in selected)
                    full_correct = sum(r["full_correct"] for r in selected)
                    benefit = sum(not r["no_correct"] and r["full_correct"] for r in selected)
                    harm = sum(r["no_correct"] and not r["full_correct"] for r in selected)
                    both_correct = sum(r["no_correct"] and r["full_correct"] for r in selected)
                    both_incorrect = sum(not r["no_correct"] and not r["full_correct"] for r in selected)
                    rf_out.append({
                        "scope": scope, "model": model, "task_group": group, "render_faithfulness": value, "n": n,
                        "no_render_correct": no_correct, "full_correct": full_correct,
                        "no_render_acc": ratio(no_correct, n), "full_acc": ratio(full_correct, n),
                        "render_benefit_count": benefit, "render_harm_count": harm,
                        "both_correct_count": both_correct, "both_incorrect_count": both_incorrect,
                        "render_benefit_share": ratio(benefit, n), "render_harm_share": ratio(harm, n),
                        "delta_acc_share": ratio(benefit - harm, n),
                        "render_benefit_rate_given_norender_wrong": ratio(benefit, n - no_correct),
                        "render_harm_rate_given_norender_correct": ratio(harm, no_correct),
                    })
            for scope, field, bins in (("all", "fu", ("ALL",)), ("by_fu", "fu", BINS)):
                for value in bins:
                    selected = category_rows if value == "ALL" else [r for r in category_rows if r[field] == value]
                    n = len(selected)
                    full_correct = sum(r["full_correct"] for r in selected)
                    wrong_correct = sum(r["wrong_correct"] for r in selected)
                    harm = sum(r["full_correct"] and not r["wrong_correct"] for r in selected)
                    correction = sum(not r["full_correct"] and r["wrong_correct"] for r in selected)
                    both_correct = sum(r["full_correct"] and r["wrong_correct"] for r in selected)
                    both_incorrect = sum(not r["full_correct"] and not r["wrong_correct"] for r in selected)
                    changed = sum(r["answer_changed"] for r in selected)
                    fu_out.append({
                        "scope": scope, "model": model, "task_group": group, "feedback_uptake": value, "n": n,
                        "full_correct": full_correct, "wrongrender_correct": wrong_correct,
                        "full_acc": ratio(full_correct, n), "wrongrender_acc": ratio(wrong_correct, n),
                        "corruption_harm_count": harm, "corruption_correction_count": correction,
                        "both_correct_count": both_correct, "both_incorrect_count": both_incorrect,
                        "corruption_harm_share": ratio(harm, n), "corruption_correction_share": ratio(correction, n),
                        "delta_acc_wrongrender_minus_full": ratio(correction - harm, n),
                        "answer_changed": changed, "answer_change_rate_semantic": ratio(changed, n),
                    })

    def write(filename: str, rows: list[dict]) -> None:
        with (BASE / filename).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write("norender_full_by_rf_common_denominator_1200_paper_categories.csv", rf_out)
    write("full_wrongrender_by_fu_common_denominator_1200_paper_categories.csv", fu_out)
    print(f"rf_rows={len(rf_out)} fu_rows={len(fu_out)}")


if __name__ == "__main__":
    main()
