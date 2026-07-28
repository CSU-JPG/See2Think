#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build semantic answer-change inputs by pairing Full and WrongRender final answers."
    )
    parser.add_argument("--full-judge-jsonl", required=True)
    parser.add_argument("--wrongrender-judge-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    full_rows = {row["task_key"]: row for row in load_jsonl(Path(args.full_judge_jsonl)) if row.get("status") == "ok"}
    wrong_rows = {
        row["task_key"]: row for row in load_jsonl(Path(args.wrongrender_judge_jsonl)) if row.get("status") == "ok"
    }
    common_keys = sorted(set(full_rows) & set(wrong_rows))

    out_path = Path(args.output_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for key in common_keys:
            full = full_rows[key]
            wrong = wrong_rows[key]
            obj = {
                "status": "ok",
                "task_key": key,
                "model_task_key": f"{args.model}::{key}",
                "model": args.model,
                "setting": "full_vs_wrongrender_answer_change",
                "category": full.get("category", ""),
                "target_task": full.get("target_task", ""),
                "source": full.get("source", ""),
                "relative_source_dir": full.get("relative_source_dir", ""),
                "sample_id": full.get("sample_id"),
                "question": full.get("question", ""),
                "reference_answer": full.get("final_answer", ""),
                "candidate_answer": wrong.get("final_answer", ""),
                "full_answer": full.get("final_answer", ""),
                "wrongrender_answer": wrong.get("final_answer", ""),
                "full_correct": full.get("correct"),
                "wrongrender_correct": wrong.get("correct"),
                "full_answer_reason": full.get("reason", ""),
                "wrongrender_answer_reason": wrong.get("reason", ""),
            }
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")

    missing_full = sorted(set(wrong_rows) - set(full_rows))
    missing_wrong = sorted(set(full_rows) - set(wrong_rows))
    print(f"wrote {len(common_keys)} paired rows to {out_path}")
    print(f"missing_full={len(missing_full)} missing_wrongrender={len(missing_wrong)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
