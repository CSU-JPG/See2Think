import argparse
import csv
import hashlib
import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_SUMMARIES = {
    "gpt-5.5": ROOT / "eval/results/answer_gpt55_final1200_vaot_full/answer_summary.json",
    "o3": ROOT / "eval/results/answer_o3_final1200_vaot_full/answer_summary.json",
    "gemini-3.5-flash": ROOT / "eval/results/answer_gemini35flash_final1200_vaot_full/answer_summary.json",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_best_models() -> dict[str, dict]:
    scores: dict[str, list[dict]] = {}
    for model, path in FULL_SUMMARIES.items():
        summary = json.loads(path.read_text(encoding="utf-8"))
        for family, row in summary["by_source"].items():
            scores.setdefault(family, []).append(
                {
                    "model": model,
                    "accuracy": float(row["accuracy"]),
                    "correct": int(row["correct"]),
                    "count": int(row["count"]),
                }
            )
    best = {}
    for family, rows in scores.items():
        rows.sort(key=lambda r: (-r["accuracy"], -r["correct"], r["model"]))
        best[family] = rows[0]
    return best


def load_manifest(model: str) -> list[dict]:
    path = ROOT / "final_results/wrong_render" / model / "_manifest.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("status") == "ok"]


STEP_RE = re.compile(
    r"(?:\*\*)?Step\s+(\d+)\s+\(Action Description\):(?:\*\*)?\s*```json\s*([\s\S]*?)```",
    re.IGNORECASE,
)


def parse_actions(steps_md: Path) -> list[dict]:
    text = steps_md.read_text(encoding="utf-8", errors="replace")
    actions = []
    for match in STEP_RE.finditer(text):
        step = int(match.group(1))
        raw = match.group(2).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        action = parsed.get("action")
        if not action:
            continue
        actions.append(
            {
                "step": step,
                "action_json": json.dumps(parsed, ensure_ascii=False, sort_keys=True),
                "action_type": action[0].get("type") if isinstance(action, list) and action else parsed.get("type", ""),
            }
        )
    return actions


def previous_existing_image(base: Path, step: int) -> Path:
    for idx in range(step - 1, -1, -1):
        candidate = base / f"p{idx}.png"
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return base / "p0.png"


def eligible_steps(model: str, rel: str, sample_id: str) -> list[dict]:
    wrong_dir = ROOT / "final_results/wrong_render" / model / Path(*rel.split("/")) / sample_id
    full_dir = ROOT / "final_results/full" / model / Path(*rel.split("/")) / sample_id
    steps_path = wrong_dir / "steps.md"
    if not steps_path.exists():
        return []
    out = []
    for action in parse_actions(steps_path):
        step = action["step"]
        wrong_img = wrong_dir / f"p{step}.png"
        correct_img = full_dir / f"p{step}.png"
        if not (wrong_img.exists() and wrong_img.stat().st_size > 0):
            continue
        if not (correct_img.exists() and correct_img.stat().st_size > 0):
            continue
        if sha256(wrong_img) == sha256(correct_img):
            continue
        before_img = previous_existing_image(full_dir, step)
        out.append(
            {
                **action,
                "before_image": str(before_img.relative_to(ROOT)),
                "correct_render_image": str(correct_img.relative_to(ROOT)),
                "wrong_render_image": str(wrong_img.relative_to(ROOT)),
                "steps_md": str(steps_path.relative_to(ROOT)),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-family", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260713)
    parser.add_argument("--out-dir", default="outputs/human_audit/wrong_render_120")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_dir = ROOT / args.out_dir
    best = load_best_models()
    selections = []
    candidates = []
    family_summary = []

    for family in sorted(best):
        best_row = best[family]
        model = best_row["model"]
        manifest = [row for row in load_manifest(model) if row["relative_source_dir"].replace("\\", "/") == family]
        family_candidates = []
        for row in manifest:
            rel = row["relative_source_dir"].replace("\\", "/")
            sid = str(row["sample_id"])
            steps = eligible_steps(model, rel, sid)
            if not steps:
                continue
            first_step = sorted(steps, key=lambda x: x["step"])[0]
            candidate = {
                "family": family,
                "model": model,
                "full_family_accuracy": best_row["accuracy"],
                "full_family_correct": best_row["correct"],
                "full_family_count": best_row["count"],
                "task_key": f"{rel}::{sid}",
                "relative_source_dir": rel,
                "sample_id": sid,
                "action_step": first_step["step"],
                "action_type": first_step["action_type"],
                "before_image": first_step["before_image"],
                "correct_render_image": first_step["correct_render_image"],
                "wrong_render_image": first_step["wrong_render_image"],
                "steps_md": first_step["steps_md"],
                "action_json": first_step["action_json"],
                "eligible_step_count": len(steps),
            }
            family_candidates.append(candidate)
        family_candidates.sort(key=lambda r: r["task_key"])
        candidates.extend(family_candidates)
        selected = rng.sample(family_candidates, k=min(args.per_family, len(family_candidates)))
        selected.sort(key=lambda r: r["task_key"])
        selections.extend(selected)
        family_summary.append(
            {
                "family": family,
                "best_model": model,
                "full_family_accuracy": best_row["accuracy"],
                "full_family_correct": best_row["correct"],
                "full_family_count": best_row["count"],
                "manifest_rows": len(manifest),
                "eligible_rows": len(family_candidates),
                "selected_rows": len(selected),
            }
        )

    write_csv(out_dir / "wrong_render_audit_candidates.csv", candidates)
    write_csv(out_dir / "wrong_render_audit_120.csv", selections)
    write_csv(out_dir / "wrong_render_audit_family_summary.csv", family_summary)
    (out_dir / "wrong_render_audit_120.json").write_text(json.dumps(selections, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "wrong_render_audit_family_summary.json").write_text(json.dumps(family_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {out_dir}")
    print(f"families={len(family_summary)} candidates={len(candidates)} selected={len(selections)}")
    for row in family_summary:
        print(
            f"{row['family']}: best={row['best_model']} full_acc={row['full_family_accuracy']:.4f} "
            f"eligible={row['eligible_rows']} selected={row['selected_rows']}"
        )


if __name__ == "__main__":
    main()
