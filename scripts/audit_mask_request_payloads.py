#!/usr/bin/env python3
import argparse
import csv
import json
import random
import re
from pathlib import Path
from typing import Any


LEAK_PATTERNS = {
    "previous_action_json": r'"action"\s*:',
    "previous_target_key": r'"target"\s*:',
    "previous_type_key": r'"type"\s*:',
    "previous_coordinate_array": r"\[\s*\d{1,4}\s*,\s*\d{1,4}\s*,\s*\d{1,4}\s*,\s*\d{1,4}\s*\]",
    "previous_render_markdown": r"!\[\]\(p\d+\.png\)",
    "renderer_text_description": r"\b(model|system|renderer)\s+(highlighted|annotated|drew|boxed|cropped|zoomed)\b",
}

ACTION_WORDS = [
    "annotate",
    "trace_highlight",
    "highlight",
    "mask",
    "overlay_text",
    "draw_line",
    "ellipse",
    "crop",
    "zoom",
    "callout",
    "box",
]


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def text_from_payload(payload: dict[str, Any]) -> str:
    chunks = []
    for msg in payload.get("messages_sent_to_model", []):
        for item in msg.get("content", []):
            if item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
    return "\n\n".join(chunks)


def previous_steps_from_prompt(text: str) -> str:
    m = re.search(
        r"Previous Steps:\s*(.*?)(?:\n\s*\*\*YOUR TASK\*\*|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def infer_task_key(path: Path) -> str:
    parts = path.parts
    if len(parts) < 3:
        return ""
    sample_id = path.parent.name
    parent = path.parent.parent.parent
    rel = []
    for p in path.parent.parents:
        if p.name.startswith("masked_action_request_audit20_"):
            break
    try:
        root_idx = parts.index(next(part for part in parts if part.startswith("masked_action_request_audit20_")))
        rel = list(parts[root_idx + 1 : -3])
    except StopIteration:
        rel = []
    except ValueError:
        rel = []
    return f"{'/'.join(rel)}::{sample_id}" if rel else sample_id


def scan_previous(previous: str) -> dict[str, Any]:
    hits = {name: bool(re.search(pattern, previous, re.IGNORECASE)) for name, pattern in LEAK_PATTERNS.items()}
    lower = previous.lower()
    thought_action_words = sorted({word for word in ACTION_WORDS if re.search(rf"\b{re.escape(word)}\b", lower)})
    hits["thought_action_words"] = thought_action_words
    hits["hard_leak"] = any(
        hits[name]
        for name in (
            "previous_action_json",
            "previous_target_key",
            "previous_type_key",
            "previous_coordinate_array",
            "previous_render_markdown",
            "renderer_text_description",
        )
    )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dumped model request payloads for masked-action leakage.")
    parser.add_argument("--roots", nargs="+", default=["newtasks/masked_action_request_audit20_*"])
    parser.add_argument("--output-dir", default="outputs/mask_request_audit_20")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026071303)
    args = parser.parse_args()

    paths: list[Path] = []
    for root_glob in args.roots:
        for root in sorted(Path().glob(root_glob)):
            paths.extend(sorted(root.rglob("request_payload_step*.json")))

    rows = []
    for path in paths:
        payload = load_payload(path)
        step = int(payload.get("step", 0))
        if step <= 1:
            continue
        text = text_from_payload(payload)
        previous = previous_steps_from_prompt(text)
        scan = scan_previous(previous)
        rows.append(
            {
                "payload_path": str(path),
                "task_key": infer_task_key(path),
                "step": step,
                "model": payload.get("model", ""),
                "request_model": payload.get("request_model", ""),
                "setting": payload.get("setting", ""),
                "masked_fields": "|".join(payload.get("masked_fields", [])),
                "rendered_image_attached": payload.get("rendered_image_attached"),
                "image_count": payload.get("image_count"),
                "previous_char_count": len(previous),
                "previous_preview": previous[:500].replace("\n", "\\n"),
                **scan,
                "thought_action_words": "|".join(scan["thought_action_words"]),
            }
        )

    rng = random.Random(args.seed)
    sampled = rng.sample(rows, min(args.sample_size, len(rows)))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fields = [
        "payload_path",
        "task_key",
        "step",
        "model",
        "request_model",
        "setting",
        "masked_fields",
        "rendered_image_attached",
        "image_count",
        "previous_char_count",
        "previous_action_json",
        "previous_target_key",
        "previous_type_key",
        "previous_coordinate_array",
        "previous_render_markdown",
        "renderer_text_description",
        "hard_leak",
        "thought_action_words",
        "previous_preview",
    ]
    for name, data in (("all_next_round_payloads.csv", rows), ("sampled_20_next_round_payloads.csv", sampled)):
        with (out_dir / name).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in data:
                writer.writerow({field: row.get(field, "") for field in fields})

    summary = {
        "payload_count_total": len(paths),
        "next_round_payload_count": len(rows),
        "sampled_count": len(sampled),
        "hard_leak_count_all_next_round": sum(1 for row in rows if row["hard_leak"]),
        "hard_leak_count_sampled": sum(1 for row in sampled if row["hard_leak"]),
        "thought_action_word_count_all_next_round": sum(1 for row in rows if row["thought_action_words"]),
        "thought_action_word_count_sampled": sum(1 for row in sampled if row["thought_action_words"]),
        "settings": {},
    }
    for row in rows:
        setting = row["setting"]
        bucket = summary["settings"].setdefault(setting, {"count": 0, "hard_leak_count": 0, "thought_action_word_count": 0})
        bucket["count"] += 1
        bucket["hard_leak_count"] += int(bool(row["hard_leak"]))
        bucket["thought_action_word_count"] += int(bool(row["thought_action_words"]))
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "sampled_20_next_round_payloads.json").write_text(json.dumps(sampled, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {out_dir}")
    return 0 if summary["hard_leak_count_sampled"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
