"""Write the final 1,200-task family-level Table 2 accuracy table."""

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200" / "complete_evaluations"
OUT = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200"
MODELS = (("GPT-5.5", "gpt55"), ("o3", "o3"), ("Gemini-3.5-Flash", "gemini35flash"))
SETTINGS = (("CoT", "text_only"), ("VAoT-NoRender", "no_render"), ("VAoT-Full", "full"), ("VAoT-WrongRender", "wrong_render"))
FAMILIES = (("Geo.", "math"), ("S-Puz.", "emma/math"), ("Phys.", "emma/physics"), ("Chem.", "emma/chemistry"), ("SciQA", "m3cot/test1"), ("AbsPat", "prism"), ("ObjAttr", "clevr_math/val"), ("Comp3D", "super_clevr"), ("R-Man.", "VLABench"), ("R-State", "droid"), ("V-Comm.", "m3cot/test0"), ("IntPhys", "intphy2"))


def load(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    csv_rows, blocks = [], []
    headers = [name for name, _ in FAMILIES] + ["Overall"]
    for display, tag in MODELS:
        scores = {}
        for setting_display, setting in SETTINGS:
            by_family = defaultdict(list)
            rows = load(INPUT / f"answer_{tag}_{setting}_1200.jsonl")
            for row in rows:
                by_family[row["relative_source_dir"].replace("\\", "/")].append(bool(row["correct"]))
            scores[setting] = [round(sum(by_family[key]) / len(by_family[key]) * 100, 2) for _, key in FAMILIES]
            scores[setting].append(round(sum(bool(row["correct"]) for row in rows) / len(rows) * 100, 2))
            csv_rows.append({"Model": display, "Setting": setting_display, **dict(zip(headers, scores[setting]))})
        best = [max(scores[s][i] for s in ("text_only", "no_render", "full")) for i in range(len(headers))]
        rows_md = []
        for setting_display, setting in SETTINGS:
            values = [f"**{v:.1f}**" if setting != "wrong_render" and v == best[i] else f"{v:.1f}" for i, v in enumerate(scores[setting])]
            rows_md.append([setting_display, *values])
        blocks.append((display, rows_md))

    with (OUT / "table2_1200_task_family_accuracy.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Model", "Setting", *headers])
        writer.writeheader(); writer.writerows(csv_rows)
    group_line = "2D Structured: Geo., S-Puz., Phys., Chem., SciQA, AbsPat · 3D Scene: ObjAttr, Comp3D · Real-world: R-Man., R-State, V-Comm., IntPhys"
    md = ["# Table 2 — Overall accuracy on the 1,200-task See2ThinkBench", "", group_line, "", "Best values are selected only among CoT, VAoT-NoRender, and VAoT-Full. WrongRender is diagnostic and is excluded from best-score highlighting.", ""]
    for model, rows_md in blocks:
        md.extend([f"## {model}", "", "| Setting | " + " | ".join(headers) + " |", "|" + "|".join(["---"] * (len(headers) + 1)) + "|"])
        md.extend(["| " + " | ".join(row) + " |" for row in rows_md]); md.append("")
    (OUT / "table2_1200_task_family_accuracy.md").write_text("\n".join(md), encoding="utf-8")
    html = ["""<!doctype html><html><head><meta charset=\"utf-8\"><title>Table 2 — 1200 tasks</title>
<style>body{font-family:Georgia,'Times New Roman',serif;margin:28px;color:#111}.wrap{max-width:1400px;margin:auto}h2{font-size:18px;margin:0 0 5px}p{margin:0 0 16px;font-size:14px}table{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0 18px}th,td{padding:3px 6px;text-align:center;white-space:nowrap}thead tr:first-child{border-top:2px solid #222;border-bottom:1px solid #222}thead tr:last-child{border-bottom:1px solid #222}th.setting,td.setting{text-align:left}.group{border-left:1px solid #444}.model td{font-style:italic;font-weight:bold;background:#f0f0f0;border-top:1px solid #999;padding:2px}tbody tr:last-child td{border-bottom:1px solid #555}strong{font-weight:700}</style></head><body><div class=\"wrap\">
<h2>Table 2. Overall accuracy on the 1,200-task See2ThinkBench.</h2>
<p>Best results among CoT, VAoT-NoRender, and VAoT-Full are highlighted in bold. VAoT-WrongRender is excluded from best-score highlighting.</p>
<table><thead><tr><th class=\"setting\" rowspan=\"2\">Setting</th><th colspan=\"6\">2D Structured Reasoning</th><th class=\"group\" colspan=\"2\">3D Scene Reasoning</th><th class=\"group\" colspan=\"4\">Real-world Visual Reasoning</th><th class=\"group\" rowspan=\"2\">Overall</th></tr><tr><th>Geo.</th><th>S-Puz.</th><th>Phys.</th><th>Chem.</th><th>SciQA</th><th>AbsPat</th><th class=\"group\">ObjAttr</th><th>Comp3D</th><th class=\"group\">R-Man.</th><th>R-State</th><th>V-Comm.</th><th>IntPhys</th></tr></thead><tbody>"""]
    for model, rows_md in blocks:
        html.append(f"<tr class=\"model\"><td colspan=\"14\">{model}</td></tr>")
        for setting, *values in rows_md:
            cells = []
            for i, value in enumerate(values):
                number = value.replace("**", "")
                cell = f"<strong>{number}</strong>" if value.startswith("**") else number
                cls = " class=\"group\"" if i in (6, 8, 12) else ""
                cells.append(f"<td{cls}>{cell}</td>")
            html.append(f"<tr><td class=\"setting\">{setting}</td>{''.join(cells)}</tr>")
    html.append("</tbody></table></div></body></html>")
    (OUT / "table2_1200_task_family_accuracy.html").write_text("\n".join(html), encoding="utf-8")
    print(OUT / "table2_1200_task_family_accuracy.md")


if __name__ == "__main__":
    main()
