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
    timeout = float(os.environ.get("SEE2THINK_KEY_STEP_JUDGE_TIMEOUT", "180"))
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
            if row.get("status") == "ok" and row.get("task_key"):
                keys.add(row["task_key"])
    return keys


def read_steps(row: dict[str, Any]) -> str:
    path = row.get("steps_md") or ""
    if path and Path(path).exists():
        return Path(path).read_text(encoding="utf-8", errors="replace")
    out_dir = row.get("output_dir") or ""
    candidate = Path(out_dir) / "steps.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8", errors="replace")
    return ""


def visual_step_numbers(steps: str) -> list[int]:
    nums: list[int] = []
    for match in re.finditer(r"\*\*Step\s+(\d+)\s+\(Action Description\):\*\*", steps, re.IGNORECASE):
        n = int(match.group(1))
        if n not in nums:
            nums.append(n)
    return nums


def compact_steps(steps: str, max_chars: int) -> str:
    if len(steps) <= max_chars:
        return steps
    head = steps[: max_chars // 2]
    tail = steps[-max_chars // 2 :]
    return f"{head}\n\n[... trajectory truncated for length ...]\n\n{tail}"


def build_prompt(row: dict[str, Any], steps: str, visual_steps: list[int], max_chars: int) -> str:
    allowed = ", ".join(str(n) for n in visual_steps) if visual_steps else "none"
    return f"""You are auditing a visual reasoning trajectory judge.

Your task is to select the key visual step(s) in the trajectory. A visual step is a step that contains an Action Description and a rendered image. The selected step(s) should be the steps that are most important for evaluating the trajectory process.

Selection criteria:
1. Select the visual step that contributes most to the final reasoning, OR
2. Select the visual step that best exposes the source of failure, OR
3. If there is no meaningful/effective visual operation, set no_valid_visual_step to true.

Do not judge whether the final answer is correct. Focus on which visual step(s) should be audited by humans.
Usually select exactly one step. Select two only when both are necessary.

Question:
{row.get("question", "")}

Ground truth:
{row.get("ground_truth", "")}

Final answer:
{row.get("final_answer", "")}

Allowed visual step numbers:
{allowed}

Trajectory:
{compact_steps(steps, max_chars)}

Return only a JSON object with:
{{
  "key_steps": [integer step numbers],
  "no_valid_visual_step": true or false,
  "reason": "brief reason"
}}
"""


def call_judge(client: Any, args: argparse.Namespace, prompt: str) -> tuple[list[int], bool, str, str]:
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": args.judge_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            if args.temperature is not None:
                kwargs["temperature"] = args.temperature
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            parsed = parse_json_object(text)
            steps = parsed.get("key_steps") or []
            if not isinstance(steps, list):
                steps = []
            steps = [int(s) for s in steps if str(s).strip().lstrip("-").isdigit()]
            return steps, bool(parsed.get("no_valid_visual_step", False)), str(parsed.get("reason", "")), text
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"key-step judge failed after {MAX_RETRIES} attempts: {last_err}")


def judge_one(row: dict[str, Any], args: argparse.Namespace, client: Any) -> dict[str, Any]:
    steps_text = read_steps(row)
    allowed = visual_step_numbers(steps_text)
    if not allowed:
        return make_row(row, args, [], True, "No visual action step was found in steps.md.", "", allowed)
    prompt = build_prompt(row, steps_text, allowed, args.max_chars)
    key_steps, no_valid, reason, raw = call_judge(client, args, prompt)
    allowed_set = set(allowed)
    key_steps = [s for s in key_steps if s in allowed_set]
    if not key_steps and not no_valid:
        no_valid = True
        reason = reason or "The judge did not select any allowed visual step."
    return make_row(row, args, key_steps, no_valid, reason, raw, allowed)


def make_row(
    src: dict[str, Any],
    args: argparse.Namespace,
    key_steps: list[int],
    no_valid: bool,
    reason: str,
    raw: str,
    visual_steps: list[int],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "task_key": src.get("task_key"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": src.get("model"),
        "setting": src.get("setting"),
        "key_step_judge_model": args.judge_model,
        "category": src.get("category"),
        "target_task": src.get("target_task"),
        "source": src.get("source"),
        "relative_source_dir": src.get("relative_source_dir"),
        "sample_id": src.get("sample_id"),
        "output_dir": src.get("output_dir"),
        "steps_md": src.get("steps_md"),
        "visual_steps": visual_steps,
        "key_steps": key_steps,
        "no_valid_visual_step": no_valid,
        "reason": reason,
        "raw_response": raw,
    }


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": row.get("status"),
        "task_key": row.get("task_key"),
        "timestamp": row.get("timestamp"),
        "model": row.get("model"),
        "setting": row.get("setting"),
        "key_step_judge_model": row.get("key_step_judge_model"),
        "category": row.get("category"),
        "target_task": row.get("target_task"),
        "source": row.get("source"),
        "relative_source_dir": row.get("relative_source_dir"),
        "sample_id": row.get("sample_id"),
        "visual_steps": json.dumps(row.get("visual_steps", []), ensure_ascii=False),
        "key_steps": json.dumps(row.get("key_steps", []), ensure_ascii=False),
        "no_valid_visual_step": row.get("no_valid_visual_step"),
        "reason": row.get("reason"),
        "output_dir": row.get("output_dir"),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "status",
        "task_key",
        "timestamp",
        "model",
        "setting",
        "key_step_judge_model",
        "category",
        "target_task",
        "source",
        "relative_source_dir",
        "sample_id",
        "visual_steps",
        "key_steps",
        "no_valid_visual_step",
        "reason",
        "output_dir",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten(row))


def summarize(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    no_valid = sum(1 for r in rows if r.get("no_valid_visual_step") is True)
    selected = total - no_valid
    avg_key_steps = sum(len(r.get("key_steps") or []) for r in rows) / total if total else None
    return {
        "count": total,
        "selected_count": selected,
        "no_valid_visual_step_count": no_valid,
        "avg_key_steps": round(avg_key_steps, 4) if avg_key_steps is not None else None,
        "failure_count": len(failures),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select key visual step(s) from VAoT-Full trajectories.")
    parser.add_argument("--input-jsonl", required=True, help="Usually a process_judge.jsonl for a Full run.")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output-root", default="eval/results")
    parser.add_argument("--judge-model", default=os.environ.get("SEE2THINK_KEY_STEP_JUDGE_MODEL", os.environ.get("SEE2THINK_JUDGE_MODEL", "gpt-5.4")))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-chars", type=int, default=18000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_jsonl)
    rows_in = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows_in = [row for row in rows_in if row.get("status") == "ok"]
    if args.limit is not None:
        rows_in = rows_in[: args.limit]

    out_dir = Path(args.output_root) / args.run_name
    jsonl_path = out_dir / "key_step_judge.jsonl"
    csv_path = out_dir / "key_step_judge.csv"
    summary_path = out_dir / "summary.json"
    failures_path = out_dir / "key_step_failures.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for path in (jsonl_path, csv_path, summary_path, failures_path):
            if path.exists():
                path.unlink()

    done = load_existing_keys(jsonl_path)
    todo = [row for row in rows_in if row.get("task_key") not in done]
    print(f"input={len(rows_in)} done={len(done)} todo={len(todo)} output={out_dir}", flush=True)

    client = create_openai_client()
    failures: list[dict[str, Any]] = []

    def run(row: dict[str, Any]) -> dict[str, Any]:
        return judge_one(row, args, client)

    if args.workers <= 1:
        for idx, row in enumerate(todo, 1):
            key = row.get("task_key")
            print(f"[{idx}/{len(todo)}] {key}", flush=True)
            try:
                append_jsonl(jsonl_path, run(row))
            except Exception as exc:
                fail = {"status": "failed", "task_key": key, "timestamp": datetime.now().isoformat(timespec="seconds"), "error": str(exc)}
                append_jsonl(failures_path, fail)
                failures.append(fail)
                print(f"FAILED {key}: {exc}", file=sys.stderr, flush=True)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, row): row for row in todo}
            for idx, fut in enumerate(as_completed(futures), 1):
                src = futures[fut]
                key = src.get("task_key")
                print(f"[{idx}/{len(todo)}] {key}", flush=True)
                try:
                    append_jsonl(jsonl_path, fut.result())
                except Exception as exc:
                    fail = {"status": "failed", "task_key": key, "timestamp": datetime.now().isoformat(timespec="seconds"), "error": str(exc)}
                    append_jsonl(failures_path, fail)
                    failures.append(fail)
                    print(f"FAILED {key}: {exc}", file=sys.stderr, flush=True)

    all_rows = []
    if jsonl_path.exists():
        all_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    all_failures = []
    if failures_path.exists():
        all_failures = [json.loads(line) for line in failures_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    write_csv(csv_path, all_rows)
    write_json(summary_path, summarize(all_rows, all_failures))
    print(f"wrote {jsonl_path}", flush=True)
    print(f"wrote {csv_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
