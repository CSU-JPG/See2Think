#!/usr/bin/env python3
import argparse
import csv
import json
import random
import shutil
from pathlib import Path
from typing import Any


MODELS = ["gpt-5.5", "o3", "gemini-3.5-flash"]
TASK_GROUPS = ["2D", "3D", "Real-world"]
TASK_GROUP_DISPLAY = {"2D": "2D", "3D": "3D", "Real-world": "Real"}
STRATA = [
    "action1_full_wrong",
    "action1_render0",
    "action1_render05",
    "action_low",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def bool_value(value: Any) -> bool | None:
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


def stratum_match(row: dict[str, str], stratum: str) -> bool:
    action = float_value(row.get("action_relevance"))
    render = float_value(row.get("render_faithfulness"))
    full_correct = bool_value(row.get("full_correct"))
    if stratum == "action1_full_wrong":
        return action == 1.0 and full_correct is False
    if stratum == "action1_render0":
        return action == 1.0 and render == 0.0
    if stratum == "action1_render05":
        return action == 1.0 and render == 0.5
    if stratum == "action_low":
        return action in {0.0, 0.5}
    raise ValueError(f"unknown stratum: {stratum}")


def sort_key(row: dict[str, str]) -> tuple[str, int]:
    return (row.get("relative_source_dir", ""), int(row.get("sample_id") or 0))


def case_dir_name(case_index: int, model: str, group: str, stratum: str, row: dict[str, str]) -> str:
    safe_model = model.replace(".", "").replace("-", "").replace(" ", "")
    safe_group = TASK_GROUP_DISPLAY[group].replace("-", "")
    task = row["task_key"].replace("/", "_").replace("::", "_")
    return f"{case_index:03d}_{safe_model}_{safe_group}_{stratum}_{task}"


def source_dir(final_results_root: Path, row: dict[str, str]) -> Path:
    return final_results_root / "full" / row["model"] / Path(*row["relative_source_dir"].split("/")) / str(row["sample_id"])


def copy_case_files(src: Path, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in sorted(src.glob("p*.png")):
        shutil.copy2(path, dst / path.name)
        copied.append(path.name)
    for name in ("steps.md", "q.md"):
        path = src / name
        if path.exists():
            shutil.copy2(path, dst / name)
            copied.append(name)
    return copied


def write_case_summary(path: Path, meta: dict[str, Any]) -> None:
    lines = [
        f"# Case {meta['case_index']}",
        "",
        f"- model: {meta['model']}",
        f"- task_group: {meta['task_group']}",
        f"- stratum: {meta['stratum']}",
        f"- stratum_match: {meta['stratum_match']}",
        f"- task_key: {meta['task_key']}",
        f"- sample_id: {meta['sample_id']}",
        f"- full_correct: {meta['full_correct']}",
        f"- action_relevance: {meta['action_relevance']}",
        f"- render_faithfulness: {meta['render_faithfulness']}",
        f"- feedback_uptake: {meta['feedback_uptake']}",
        "",
        "## Answers",
        "",
        f"- no_render_answer: {meta['no_render_answer']}",
        f"- full_answer: {meta['full_answer']}",
        f"- wrongrender_answer: {meta['wrongrender_answer']}",
        "",
        "## Reasons",
        "",
        f"- key_step_reason: {meta['key_step_reason']}",
        f"- action_relevance_reason: {meta['action_relevance_reason']}",
        f"- render_faithfulness_reason: {meta['render_faithfulness_reason']}",
        f"- feedback_uptake_reason: {meta['feedback_uptake_reason']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_index_html(path: Path, rows: list[dict[str, Any]]) -> None:
    html = [
        "<!doctype html>",
        "<meta charset='utf-8'>",
        "<title>Human validation 180</title>",
        "<style>body{font-family:Arial,sans-serif;margin:24px} table{border-collapse:collapse;width:100%} td,th{border:1px solid #ddd;padding:6px;vertical-align:top} img{max-width:220px;max-height:160px;margin:4px;border:1px solid #ccc} .false{background:#fff4d6}</style>",
        "<h1>Human validation 180</h1>",
        "<table>",
        "<tr><th>#</th><th>model</th><th>group</th><th>stratum</th><th>match</th><th>task</th><th>metrics</th><th>files</th><th>images</th></tr>",
    ]
    for row in rows:
        cls = "false" if not row["stratum_match"] else ""
        images = "".join(f"<img src='{row['case_dir']}/{name}'>" for name in row["copied_images"] if str(name).endswith(".png"))
        files = f"<a href='{row['case_dir']}/case_summary.md'>summary</a> | <a href='{row['case_dir']}/metadata.json'>metadata</a> | <a href='{row['case_dir']}/steps.md'>steps</a>"
        metrics = f"AR={row['action_relevance']} RF={row['render_faithfulness']} FU={row['feedback_uptake']} full={row['full_correct']}"
        html.append(
            f"<tr class='{cls}'><td>{row['case_index']}</td><td>{row['model']}</td><td>{row['task_group']}</td><td>{row['stratum']}</td><td>{row['stratum_match']}</td><td>{row['task_key']}</td><td>{metrics}</td><td>{files}</td><td>{images}</td></tr>"
        )
    html.extend(["</table>"])
    path.write_text("\n".join(html), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select 180 human-validation cases with corrected task groups.")
    parser.add_argument("--master-csv", default="eval/results/transition_common_denominator_600/master_transition_table.csv")
    parser.add_argument("--final-results-root", default="final_results")
    parser.add_argument("--out-dir", default="yzrcheck")
    parser.add_argument("--per-cell", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    master = load_csv(Path(args.master_csv))
    final_results_root = Path(args.final_results_root)
    out_dir = Path(args.out_dir)
    if out_dir.exists() and args.overwrite:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    selected: list[dict[str, Any]] = []
    cell_counts: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()
    case_index = 0

    for model in MODELS:
        for group in TASK_GROUPS:
            pool = [r for r in master if r["model"] == model and r["task_group"] == group]
            for stratum in STRATA:
                exact = [r for r in pool if stratum_match(r, stratum)]
                exact = sorted(exact, key=sort_key)
                rng.shuffle(exact)
                chosen: list[tuple[dict[str, str], bool]] = []
                for row in exact:
                    key = (row["model"], row["task_key"])
                    if key in used:
                        continue
                    chosen.append((row, True))
                    used.add(key)
                    if len(chosen) == args.per_cell:
                        break
                supplement_pool = sorted(pool, key=sort_key)
                rng.shuffle(supplement_pool)
                for row in supplement_pool:
                    if len(chosen) == args.per_cell:
                        break
                    key = (row["model"], row["task_key"])
                    if key in used:
                        continue
                    chosen.append((row, False))
                    used.add(key)
                cell_counts.append(
                    {
                        "model": model,
                        "task_group": TASK_GROUP_DISPLAY[group],
                        "stratum": stratum,
                        "strict_candidate_count": len(exact),
                        "selected": len(chosen),
                        "strict_selected": sum(1 for _, matched in chosen if matched),
                        "supplement_selected": sum(1 for _, matched in chosen if not matched),
                    }
                )
                if len(chosen) != args.per_cell:
                    raise RuntimeError(f"not enough cases for {model} {group} {stratum}: {len(chosen)}")
                for row, matched in chosen:
                    case_index += 1
                    display_group = TASK_GROUP_DISPLAY[group]
                    case_dir = case_dir_name(case_index, model, group, stratum, row)
                    dst = out_dir / case_dir
                    src = source_dir(final_results_root, row)
                    copied = copy_case_files(src, dst)
                    meta = {
                        "case_index": case_index,
                        "model": model,
                        "task_group": display_group,
                        "original_task_group": group,
                        "stratum": stratum,
                        "stratum_match": matched,
                        "task_key": row["task_key"],
                        "relative_source_dir": row["relative_source_dir"],
                        "sample_id": row["sample_id"],
                        "source_dir": str(src),
                        "case_dir": case_dir,
                        "no_render_answer": row["no_render_answer"],
                        "no_render_correct": bool_value(row["no_render_correct"]),
                        "full_answer": row["full_answer"],
                        "full_correct": bool_value(row["full_correct"]),
                        "wrongrender_answer": row["wrongrender_answer"],
                        "wrongrender_correct": bool_value(row["wrongrender_correct"]),
                        "answer_changed": bool_value(row["answer_changed"]),
                        "action_relevance": float_value(row["action_relevance"]),
                        "render_faithfulness": float_value(row["render_faithfulness"]),
                        "feedback_uptake": float_value(row["feedback_uptake"]),
                        "key_step_id": row["key_step_id"],
                        "key_step_reason": row["key_step_reason"],
                        "action_relevance_reason": row["action_relevance_reason"],
                        "render_faithfulness_reason": row["render_faithfulness_reason"],
                        "feedback_uptake_reason": row["feedback_uptake_reason"],
                        "copied_images": [name for name in copied if name.endswith(".png")],
                        "copied_files": copied,
                    }
                    write_json(dst / "metadata.json", meta)
                    write_case_summary(dst / "case_summary.md", meta)
                    selected.append(meta)

    index_fields = [
        "case_index",
        "model",
        "task_group",
        "stratum",
        "stratum_match",
        "task_key",
        "relative_source_dir",
        "sample_id",
        "full_correct",
        "action_relevance",
        "render_faithfulness",
        "feedback_uptake",
        "case_dir",
        "copied_images",
    ]
    write_csv(out_dir / "index.csv", selected, index_fields)
    write_csv(out_dir / "cell_counts.csv", cell_counts)
    write_index_html(out_dir / "index.html", selected)
    readme = [
        "# Human Validation 180",
        "",
        "Corrected task groups are used: intphy2 is Real, not 3D.",
        "",
        "Sampling structure: 3 models x 3 task groups x 4 strata x 5 cases = 180.",
        "",
        "Strata:",
        "- action1_full_wrong: Action Relevance = 1 and Full is wrong",
        "- action1_render0: Action Relevance = 1 and Render Faithfulness = 0",
        "- action1_render05: Action Relevance = 1 and Render Faithfulness = 0.5",
        "- action_low: Action Relevance = 0 or 0.5",
        "",
        "`stratum_match=false` means the strict cell did not have enough unused candidates and was supplemented from the same model and task group.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    strict = sum(1 for r in selected if r["stratum_match"])
    print(f"wrote {len(selected)} cases to {out_dir}")
    print(f"strict_match={strict} supplement={len(selected)-strict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
