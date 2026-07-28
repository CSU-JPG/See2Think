"""Calculate the appendix paired-intervention metrics on final 1,200-task runs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200" / "complete_evaluations"
OUTPUT = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200"
SEMANTIC_CHANGE = OUTPUT / "semantic_answer_change_1200"
MODELS = (
    ("GPT-5.5", "gpt55", "gpt55_full_vs_wrongrender_1200"),
    ("o3", "o3", "o3_full_vs_wrongrender_1200"),
    ("Gemini-3.5-Flash", "gemini35flash", "gemini35flash_full_vs_wrongrender_1200"),
)
BINS = (0.0, 0.5, 1.0)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def as_map(rows: list[dict]) -> dict[str, dict]:
    return {str(row["task_key"]): row for row in rows}


def percent(value: int, denominator: int) -> float:
    return round(100 * value / denominator, 2)


def main() -> None:
    rf_rows: list[dict] = []
    fu_rows: list[dict] = []
    for model, tag, semantic_run in MODELS:
        no_render = as_map(load_jsonl(INPUT / f"answer_{tag}_no_render_1200.jsonl"))
        full = as_map(load_jsonl(INPUT / f"answer_{tag}_full_1200.jsonl"))
        wrong = as_map(load_jsonl(INPUT / f"answer_{tag}_wrong_render_1200.jsonl"))
        process = load_jsonl(INPUT / f"process_eval_{tag}_full_1200.jsonl")
        semantic = as_map(load_jsonl(SEMANTIC_CHANGE / semantic_run / "answer_change_judge.jsonl"))
        if not (len(no_render) == len(full) == len(wrong) == len(process) == len(semantic) == 1200):
            raise RuntimeError(f"{model}: expected 1,200 aligned rows per input")

        for metric, output_rows in (("render_faithfulness", rf_rows), ("feedback_uptake", fu_rows)):
            groups: dict[float, list[dict]] = defaultdict(list)
            for row in process:
                if row.get("status") == "ok":
                    groups[float(row[metric])].append(row)
            for score in BINS:
                group = groups[score]
                n = len(group)
                if n == 0:
                    continue
                if metric == "render_faithfulness":
                    benefit = sum(not bool(no_render[r["task_key"]]["correct"]) and bool(full[r["task_key"]]["correct"]) for r in group)
                    harm = sum(bool(no_render[r["task_key"]]["correct"]) and not bool(full[r["task_key"]]["correct"]) for r in group)
                    output_rows.append({
                        "model": model, "RF": score, "N": n,
                        "render_benefit_n": benefit, "render_benefit_share_pct": percent(benefit, n),
                        "render_harm_n": harm, "render_harm_share_pct": percent(harm, n),
                        "delta_acc_pp": round(percent(benefit, n) - percent(harm, n), 2),
                    })
                else:
                    answer_change = sum(bool(semantic[r["task_key"]]["answer_changed"]) for r in group)
                    harm = sum(bool(full[r["task_key"]]["correct"]) and not bool(wrong[r["task_key"]]["correct"]) for r in group)
                    full_correct = sum(bool(full[r["task_key"]]["correct"]) for r in group)
                    wrong_correct = sum(bool(wrong[r["task_key"]]["correct"]) for r in group)
                    output_rows.append({
                        "model": model, "FU": score, "N": n,
                        "answer_change_n": answer_change, "answer_change_share_pct": percent(answer_change, n),
                        "corruption_harm_n": harm, "corruption_harm_share_pct": percent(harm, n),
                        "full_acc_pct": percent(full_correct, n), "wrongrender_acc_pct": percent(wrong_correct, n),
                        "accuracy_degradation_pp": round(percent(full_correct, n) - percent(wrong_correct, n), 2),
                    })

    for name, rows in (("paired_rf_norender_to_full_1200", rf_rows), ("paired_fu_full_to_wrongrender_1200", fu_rows)):
        with (OUTPUT / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    lines = [
        "# Paired intervention analysis (final 1,200 tasks)",
        "",
        "All denominators are the matched trajectories in the relevant RF/FU bin. Answer Change uses the semantic-equivalence judge (with normalized exact matching as a fast path). Percentages are percentages; ΔAcc and degradation are percentage points.",
        "",
        "## NoRender → Full, grouped by RF",
        "",
        "| Model | RF | N | Render benefit | Render harm | ΔAcc |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rf_rows:
        lines.append(f"| {r['model']} | {r['RF']:.1f} | {r['N']} | {r['render_benefit_n']} ({r['render_benefit_share_pct']:.2f}%) | {r['render_harm_n']} ({r['render_harm_share_pct']:.2f}%) | {r['delta_acc_pp']:+.2f} pp |")
    lines += [
        "",
        "## Full → WrongRender, grouped by FU",
        "",
        "| Model | FU | N | Answer change | Corruption harm | Full acc. | WrongRender acc. | Degradation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in fu_rows:
        lines.append(f"| {r['model']} | {r['FU']:.1f} | {r['N']} | {r['answer_change_n']} ({r['answer_change_share_pct']:.2f}%) | {r['corruption_harm_n']} ({r['corruption_harm_share_pct']:.2f}%) | {r['full_acc_pct']:.2f}% | {r['wrongrender_acc_pct']:.2f}% | {r['accuracy_degradation_pp']:+.2f} pp |")
    (OUTPUT / "paired_intervention_analysis_1200.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
