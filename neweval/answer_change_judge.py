#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_RETRIES = 3


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def create_openai_client():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not set")
    timeout = float(os.environ.get("SEE2THINK_ANSWER_JUDGE_TIMEOUT", "120"))
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    if not raw.startswith("{"):
        obj = re.search(r"\{.*\}", raw, re.DOTALL)
        if obj:
            raw = obj.group(0)
    return json.loads(raw)


def load_existing_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "ok" and row.get("model_task_key"):
                keys.add(row["model_task_key"])
    return keys


def normalize_for_fast_match(text: Any) -> str:
    s = "" if text is None else str(text)
    s = s.lower()
    s = re.sub(r"\\boxed\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"[`*_#$\\\[\]\(\){}]", "", s)
    s = re.sub(r"\s+", "", s)
    return s.strip(" .?:;,")


def fast_equivalence(row: dict[str, Any]) -> tuple[bool, str] | None:
    ref = normalize_for_fast_match(row.get("reference_answer", ""))
    cand = normalize_for_fast_match(row.get("candidate_answer", ""))
    if ref == cand:
        return True, "fast_exact"
    if not ref or not cand:
        return False, "one_empty"
    return None


def build_prompt(row: dict[str, Any]) -> str:
    return f"""You are a strict answer equivalence evaluator for a multimodal reasoning benchmark.

Judge whether Answer B is semantically equivalent to Answer A for the given question.

Question:
{row.get("question", "")}

Answer A:
{row.get("reference_answer", "")}

Answer B:
{row.get("candidate_answer", "")}

Rules:
1. Ignore harmless formatting differences, units formatting, LaTeX wrappers, punctuation, and equivalent wording.
2. For math, treat algebraically equivalent expressions and numerically equivalent answers as equivalent when the intended quantity matches.
3. For multiple-choice questions, treat the same option letter and the same option text as equivalent.
4. If one answer adds claims that contradict the other answer, mark them not equivalent.
5. If one answer is empty/evasive and the other is not, mark them not equivalent.
6. Be strict about counts, directions, relations, and named entities.

Return only a JSON object with:
{{
  "equivalent": true or false,
  "reason": "brief explanation"
}}
"""


def call_judge(client: Any, judge_model: str, prompt: str, temperature: float | None) -> tuple[bool, str, str]:
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": judge_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            parsed = parse_json_object(text)
            return bool(parsed.get("equivalent", False)), str(parsed.get("reason", "")), text
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
    raise RuntimeError(f"answer change judge failed after {MAX_RETRIES} attempts: {last_err}")


def make_row(src: dict[str, Any], args: argparse.Namespace, equivalent: bool, reason: str, raw: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "task_key": src.get("task_key"),
        "model_task_key": src.get("model_task_key"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": src.get("model"),
        "setting": src.get("setting"),
        "answer_change_judge_model": args.judge_model,
        "category": src.get("category"),
        "target_task": src.get("target_task"),
        "source": src.get("source"),
        "relative_source_dir": src.get("relative_source_dir"),
        "sample_id": src.get("sample_id"),
        "question": src.get("question", ""),
        "full_answer": src.get("full_answer", ""),
        "wrongrender_answer": src.get("wrongrender_answer", ""),
        "full_correct": src.get("full_correct"),
        "wrongrender_correct": src.get("wrongrender_correct"),
        "answers_equivalent": bool(equivalent),
        "answer_changed": not bool(equivalent),
        "reason": reason,
        "raw_response": raw,
    }


def judge_one(row: dict[str, Any], args: argparse.Namespace, client: Any | None) -> dict[str, Any]:
    fast = fast_equivalence(row) if args.fast_exact else None
    if fast is not None:
        equivalent, reason = fast
        return make_row(row, args, equivalent, reason, "")
    if client is None:
        raise RuntimeError("client is required when dry_run is false")
    equivalent, reason, raw = call_judge(client, args.judge_model, build_prompt(row), args.temperature)
    return make_row(row, args, equivalent, reason, raw)


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "status",
        "task_key",
        "model_task_key",
        "timestamp",
        "model",
        "setting",
        "answer_change_judge_model",
        "category",
        "target_task",
        "source",
        "relative_source_dir",
        "sample_id",
        "full_correct",
        "wrongrender_correct",
        "answers_equivalent",
        "answer_changed",
        "reason",
        "full_answer",
        "wrongrender_answer",
    ]
    return {field: row.get(field) for field in fields}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(flatten({}).keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten(row))


def summarize(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    changed = sum(1 for row in rows if row.get("answer_changed") is True)
    summary: dict[str, Any] = {
        "count": total,
        "answer_changed": changed,
        "answer_change_rate": round(changed / total, 4) if total else None,
        "failure_count": len(failures),
        "by_source": {},
        "by_category": {},
    }
    for group_key, target in (("relative_source_dir", "by_source"), ("category", "by_category")):
        for row in rows:
            key = str(row.get(group_key, ""))
            bucket = summary[target].setdefault(
                key, {"count": 0, "answer_changed": 0, "answer_change_rate": None}
            )
            bucket["count"] += 1
            if row.get("answer_changed") is True:
                bucket["answer_changed"] += 1
        for bucket in summary[target].values():
            bucket["answer_change_rate"] = round(bucket["answer_changed"] / bucket["count"], 4) if bucket["count"] else None
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Judge semantic answer changes between Full and WrongRender answers")
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output-root", default="neweval/results")
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("SEE2THINK_ANSWER_JUDGE_MODEL", os.environ.get("SEE2THINK_JUDGE_MODEL", "gpt-5.4")),
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--fast-exact", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_jsonl)
    rows_in = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit is not None:
        rows_in = rows_in[: args.limit]

    out_dir = Path(args.output_root) / args.run_name
    jsonl_path = out_dir / "answer_change_judge.jsonl"
    csv_path = out_dir / "answer_change_judge.csv"
    summary_path = out_dir / "answer_change_summary.json"
    failures_path = out_dir / "answer_change_failures.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for path in (jsonl_path, csv_path, summary_path, failures_path):
            if path.exists():
                path.unlink()

    done = load_existing_keys(jsonl_path)
    todo = [row for row in rows_in if row.get("model_task_key") not in done]
    print(f"input={len(rows_in)} done={len(done)} todo={len(todo)} output={out_dir}", flush=True)

    needs_client = bool(todo)
    if args.fast_exact:
        needs_client = any(fast_equivalence(row) is None for row in todo)
    client = create_openai_client() if needs_client else None
    failures: list[dict[str, Any]] = []

    def run(row: dict[str, Any]) -> dict[str, Any]:
        return judge_one(row, args, client)

    if args.workers <= 1:
        for idx, row in enumerate(todo, 1):
            key = row.get("model_task_key")
            print(f"[{idx}/{len(todo)}] {key}", flush=True)
            try:
                append_jsonl(jsonl_path, run(row))
            except Exception as exc:
                fail = {"status": "failed", "model_task_key": key, "timestamp": datetime.now().isoformat(timespec="seconds"), "error": str(exc)}
                append_jsonl(failures_path, fail)
                failures.append(fail)
                print(f"FAILED {key}: {exc}", file=sys.stderr, flush=True)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, row): row for row in todo}
            for idx, fut in enumerate(as_completed(futures), 1):
                src = futures[fut]
                key = src.get("model_task_key")
                print(f"[{idx}/{len(todo)}] {key}", flush=True)
                try:
                    append_jsonl(jsonl_path, fut.result())
                except Exception as exc:
                    fail = {"status": "failed", "model_task_key": key, "timestamp": datetime.now().isoformat(timespec="seconds"), "error": str(exc)}
                    append_jsonl(failures_path, fail)
                    failures.append(fail)
                    print(f"FAILED {key}: {exc}", file=sys.stderr, flush=True)

    all_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()] if jsonl_path.exists() else []
    all_failures = (
        [json.loads(line) for line in failures_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if failures_path.exists()
        else []
    )
    write_csv(csv_path, all_rows)
    write_json(summary_path, summarize(all_rows, all_failures))
    print(f"wrote {jsonl_path}", flush=True)
    print(f"wrote {csv_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
