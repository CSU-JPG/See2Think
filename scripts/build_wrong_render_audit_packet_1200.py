"""Create a paper-taxonomy-stratified, human-reviewable WrongRender audit packet."""

import csv
import hashlib
import json
import os
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
FINAL = ROOT / "final_results_1200"
OUT = ROOT / "outputs" / "human_audit" / "wrong_render_1200"
MODELS = (("gpt-5.5", "gpt55"), ("o3", "o3"), ("gemini-3.5-flash", "gemini35flash"))
FAMILIES = (
    "math", "emma/math", "emma/physics", "emma/chemistry", "m3cot/test1", "prism",
    "clevr_math/val", "super_clevr", "VLABench", "droid", "m3cot/test0", "intphy2",
)
STEP_RE = re.compile(r"(?:\*\*)?Step\s+(\d+)\s+\(Action Description\):(?:\*\*)?\s*```json\s*([\s\S]*?)```", re.I)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hardlink_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def full_accuracy_by_family() -> dict[str, dict]:
    by_family = defaultdict(list)
    for model, tag in MODELS:
        rows = load_jsonl(RESULTS / f"answer_{tag}_final1200_vaot_full" / "answer_judge.jsonl")
        for family in FAMILIES:
            group = [row for row in rows if row["relative_source_dir"].replace("\\", "/") == family]
            by_family[family].append({"model": model, "accuracy": sum(bool(r["correct"]) for r in group) / len(group)})
    best = {}
    for family, rows in by_family.items():
        best[family] = sorted(rows, key=lambda row: (-row["accuracy"], row["model"]))[0]
    return best


def parse_actions(steps_path: Path) -> list[dict]:
    text = steps_path.read_text(encoding="utf-8", errors="replace")
    actions = []
    for match in STEP_RE.finditer(text):
        try:
            data = json.loads(match.group(2).strip())
        except json.JSONDecodeError:
            continue
        action = data.get("action")
        if not isinstance(action, list) or not action:
            continue
        actions.append({"step": int(match.group(1)), "action_type": action[0].get("type", ""), "action_json": json.dumps(data, ensure_ascii=False, indent=2)})
    return actions


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--per-family", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260718)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    best = full_accuracy_by_family()
    candidates, selected, summary = [], [], []

    for family in FAMILIES:
        model = best[family]["model"]
        wrong_base = FINAL / "wrong_render" / model / Path(*family.split("/"))
        full_base = FINAL / "full" / model / Path(*family.split("/"))
        family_candidates = []
        for wrong_dir in sorted(wrong_base.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
            if not wrong_dir.is_dir() or not wrong_dir.name.isdigit():
                continue
            full_dir = full_base / wrong_dir.name
            steps = wrong_dir / "steps.md"
            if not (steps.exists() and full_dir.exists()):
                continue
            for action in parse_actions(steps):
                step = action["step"]
                wrong_img = wrong_dir / f"p{step}.png"
                correct_img = full_dir / f"p{step}.png"
                origin_img = full_dir / "p0.png"
                if not all(p.exists() and p.stat().st_size > 0 for p in (origin_img, wrong_img, correct_img)):
                    continue
                if sha256(wrong_img) == sha256(correct_img):
                    continue
                family_candidates.append({
                    "family": family, "model": model, "full_family_accuracy": round(best[family]["accuracy"], 4),
                    "task_key": f"{family}::{wrong_dir.name}", "relative_source_dir": family,
                    "sample_id": wrong_dir.name, "action_step": step, "action_type": action["action_type"],
                    "original_image": str(origin_img.relative_to(ROOT)), "correct_render_image": str(correct_img.relative_to(ROOT)),
                    "wrong_render_image": str(wrong_img.relative_to(ROOT)), "steps_md": str(steps.relative_to(ROOT)),
                    "action_json": action["action_json"],
                })
        family_candidates.sort(key=lambda row: (row["task_key"], row["action_step"]))
        candidates.extend(family_candidates)
        chosen = rng.sample(family_candidates, k=min(args.per_family, len(family_candidates)))
        chosen.sort(key=lambda row: (row["task_key"], row["action_step"]))
        selected.extend(chosen)
        summary.append({"family": family, "model": model, "eligible": len(family_candidates), "selected": len(chosen)})

    # Materialize a review packet so auditors do not need to find assets manually.
    packet_root = OUT / "review_packets"
    for i, row in enumerate(selected, start=1):
        packet = packet_root / f"{i:03d}_{row['model']}_{row['relative_source_dir'].replace('/', '_')}_{row['sample_id']}_s{row['action_step']}"
        hardlink_or_copy(ROOT / row["original_image"], packet / "original_p0.png")
        hardlink_or_copy(ROOT / row["correct_render_image"], packet / "correct_render.png")
        hardlink_or_copy(ROOT / row["wrong_render_image"], packet / "wrong_render.png")
        (packet / "request_action.json").write_text(row["action_json"], encoding="utf-8")
        (packet / "metadata.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        row["audit_id"] = f"WR{i:03d}"
        row["review_packet"] = str(packet.relative_to(ROOT))

    template = []
    for row in selected:
        item = {key: value for key, value in row.items() if key != "action_json"}
        item.update({
            "error_validity": "", "visual_plausibility": "", "operation_consistency": "",
            "task_relevance": "", "content_retention": "", "overall_decision": "",
            "auditor_id": "", "notes": "",
        })
        template.append(item)
    write_csv(OUT / "wrong_render_audit_candidates.csv", candidates)
    write_csv(OUT / "wrong_render_audit_tasks.csv", selected)
    write_csv(OUT / "wrong_render_audit_template.csv", template)
    write_csv(OUT / "wrong_render_audit_family_summary.csv", summary)
    (OUT / "README.md").write_text(
        "# WrongRender human audit\n\n"
        "Review `review_packets/` and fill `wrong_render_audit_template.csv`.\n\n"
        "For each of the five criteria use `Pass`, `Partial`, or `Fail`.\n"
        "Set `overall_decision` to `Pass` only when all five criteria pass; use `Partial` when the three core criteria "
        "(error validity, operation consistency, task relevance) pass but visual plausibility or content retention is weak; otherwise use `Fail`.\n",
        encoding="utf-8",
    )
    print(f"selected={len(selected)} candidates={len(candidates)} out={OUT}")


if __name__ == "__main__":
    main()
