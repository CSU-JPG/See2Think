import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "outputs" / "final_tracking" / "assembled_final_results_summary.csv"
OUT = ROOT / "outputs" / "final_tracking" / "final_results_overview.md"


def load_rows():
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pct(valid, total):
    return f"{valid / total * 100:.1f}%" if total else "0.0%"


def main():
    rows = load_rows()
    by_setting = defaultdict(list)
    for row in rows:
        by_setting[row["setting"]].append(row)

    lines = []
    lines.append("# Final Results Overview")
    lines.append("")
    lines.append("Final merged result directory: `final_results/`")
    lines.append("")
    lines.append("Rule: `text_only`, `no_render`, and `wrong_render` all use the same aligned 600-sample manifest. Only real output folders are copied into `final_results/`.")
    lines.append("")

    total_steps = {}
    for folder in ["newtasks", "newtasks_reused", "final_results"]:
        total_steps[folder] = sum(1 for _ in (ROOT / folder).rglob("steps.md")) if (ROOT / folder).exists() else 0
    lines.append("## Local Real Result Files")
    lines.append("")
    lines.append("| Folder | steps.md count | Meaning |")
    lines.append("| --- | ---: | --- |")
    lines.append(f"| `newtasks/` | {total_steps['newtasks']} | Newly run raw results |")
    lines.append(f"| `newtasks_reused/` | {total_steps['newtasks_reused']} | Reused old valid results |")
    lines.append(f"| `final_results/` | {total_steps['final_results']} | Final merged local results |")
    lines.append("")

    setting_order = ["text_only", "no_render", "wrong_render"]
    for setting in setting_order:
        lines.append(f"## {setting}")
        lines.append("")
        lines.append("| Model | Valid | Missing | Completion | From newtasks | From reused | Missing file |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
        for row in sorted(by_setting.get(setting, []), key=lambda r: r["model"]):
            valid = int(row["valid"])
            total = int(row["target_total"])
            missing = int(row["missing"])
            new = int(row["copied_from_newtasks"])
            reused = int(row["copied_from_reused"])
            missing_file = row["missing_file"]
            lines.append(
                f"| {row['model']} | {valid}/{total} | {missing} | {pct(valid, total)} | {new} | {reused} | `{missing_file}` |"
            )
        lines.append("")

    lines.append("## Current Notes")
    lines.append("")
    lines.append("- `gpt-5.5 / o3 / gemini-3.5` have 595/600 for both `text_only` and `no_render`; they miss the same 5 samples.")
    lines.append("- `wrong_render` is not complete yet; current rows are mainly reused old results plus a small Gemini test run.")
    lines.append("- Qwen `text_only/wrong_render` currently come from reused old results; Qwen `no_render` has no local usable results yet.")
    lines.append("")

    common_missing = ROOT / "final_results" / "text_only" / "gpt-5.5" / "_missing.csv"
    if common_missing.exists():
        with common_missing.open("r", encoding="utf-8-sig", newline="") as f:
            missing_rows = list(csv.DictReader(f))
        lines.append("## Shared Missing 5 Samples For Closed-Source text_only/no_render")
        lines.append("")
        lines.append("| order | source | id |")
        lines.append("| ---: | --- | ---: |")
        for row in missing_rows:
            lines.append(f"| {row['order']} | `{row['relative_source_dir']}` | {row['sample_id']} |")
        lines.append("")

    retry_dir = ROOT / "json" / "run_tasks_need_600_retry"
    retry_files = sorted(p.relative_to(ROOT).as_posix() for p in retry_dir.glob("*missing_final_results.json")) if retry_dir.exists() else []
    lines.append("## Retry JSON Files Already Generated")
    lines.append("")
    if retry_files:
        for item in retry_files:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
