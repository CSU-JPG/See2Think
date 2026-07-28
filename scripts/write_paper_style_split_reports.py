"""Render CSV analysis outputs as paper-style Markdown tables."""

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "analysis_split_and_merged_1200"
MODELS = ["gpt-5.5", "o3", "gemini-3.5-flash"]
SETTINGS = ["text_only", "no_render", "full", "wrong_render"]
CATS = ["2D", "3D", "Real"]


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def markdown_table(headers, data):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(value) for value in row) + " |" for row in data]
    return "\n".join(out)


def pct(row):
    return f"{float(row['accuracy']) * 100:.2f}%"


def main():
    for split in ["old_600", "new_600", "merged_1200"]:
        folder = BASE / split
        acc_cat = rows(folder / "accuracy_by_model_setting_category.csv")
        acc_overall = rows(folder / "accuracy_by_model_setting_overall.csv")
        process = rows(folder / "process_by_model_answer_category.csv")
        acc_map = {(r["model"], r["setting"], r["category"]): r for r in acc_cat}
        overall_map = {(r["model"], r["setting"]): r for r in acc_overall}

        acc_data = []
        for model in MODELS:
            for setting in SETTINGS:
                cells = [model, setting]
                for cat in CATS:
                    r = acc_map[(model, setting, cat)]
                    cells += [r["count"], pct(r)]
                r = overall_map[(model, setting)]
                cells += [r["count"], pct(r)]
                acc_data.append(cells)

        process_map = {(r["model"], r["answer"], r["category"]): r for r in process}
        process_data = []
        for model in MODELS:
            for answer in ["Correct", "Incorrect"]:
                for cat in CATS:
                    r = process_map[(model, answer, cat)]
                    process_data.append([model, answer, cat, r["count"], f"{float(r['action']):.4f}", f"{float(r['render']):.4f}", f"{float(r['feedback']):.4f}"])

        title = {"old_600": "Historical 600", "new_600": "Complementary 600", "merged_1200": "Merged 1200"}[split]
        report = [
            f"# {title}: Paper-style analysis",
            "",
            "## Accuracy by category",
            "",
            markdown_table(["Model", "Setting", "2D n", "2D Acc", "3D n", "3D Acc", "Real n", "Real Acc", "Overall n", "Overall Acc"], acc_data),
            "",
            "## VAoT-Full process metrics by answer correctness and category",
            "",
            markdown_table(["Model", "Answer", "Category", "Count", "Action", "Render", "Feedback"], process_data),
            "",
            "`Action`, `Render`, and `Feedback` are means of the 0/0.5/1 process scores.",
            "",
        ]
        (folder / "paper_style_report.md").write_text("\n".join(report), encoding="utf-8")
        print(folder / "paper_style_report.md")


if __name__ == "__main__":
    main()
