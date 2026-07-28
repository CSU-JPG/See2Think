#!/usr/bin/env python3
import argparse
import base64
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


DATA_PREFIX = "annotation/dataset/data/"
MAX_RETRIES = 3
ALLOWED_SCORES = (0.0, 0.5, 1.0)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def rel_source_dir(data_path: str) -> str:
    p = data_path.replace("\\", "/")
    if p.startswith(DATA_PREFIX):
        p = p[len(DATA_PREFIX):]
    if p.endswith("/data.json"):
        p = p[: -len("/data.json")]
    return p


def task_key(task: dict[str, Any]) -> str:
    return f"{rel_source_dir(task['path'])}::{int(task['id'])}"


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
                keys.add(str(row["task_key"]))
    return keys


def load_sample(data_base: Path, task: dict[str, Any]) -> dict[str, Any]:
    data = load_json(data_base / task["path"])
    return data[int(task["id"])]


def sample_question(sample: dict[str, Any]) -> str:
    for key in ("question", "problem", "query", "prompt"):
        value = sample.get(key)
        if value:
            return str(value)
    return ""


def sample_answer(sample: dict[str, Any]) -> str:
    for key in ("answer", "ground_truth", "gt_answer", "target"):
        value = sample.get(key)
        if value is not None:
            return str(value)
    return ""


def extract_final_answer(steps_text: str) -> str:
    matches = list(
        re.finditer(
            r"\*\*Final Answer:\*\*\s*(.*?)(?=\n\*\*Step|\Z)",
            steps_text,
            re.DOTALL | re.IGNORECASE,
        )
    )
    if matches:
        return matches[-1].group(1).strip()
    idx = steps_text.lower().rfind("final answer:")
    if idx >= 0:
        return steps_text[idx + len("final answer:"):].strip()
    return ""


def find_output_dir(results_root: Path, model: str, task: dict[str, Any]) -> Path | None:
    rel = rel_source_dir(task["path"])
    sid = str(int(task["id"]))
    candidates = [
        results_root / model / rel / sid,
        results_root / rel / sid,
    ]
    for cand in candidates:
        if (cand / "steps.md").exists():
            return cand
    return None


def rendered_images(output_dir: Path, max_images: int) -> list[Path]:
    out: list[tuple[int, Path]] = []
    for path in output_dir.glob("p*.png"):
        m = re.fullmatch(r"p(\d+)\.png", path.name)
        if m:
            out.append((int(m.group(1)), path))
    out.sort(key=lambda x: x[0])
    return [p for _, p in out[:max_images]]


def visual_step_numbers(steps_text: str) -> list[int]:
    nums: list[int] = []
    pattern = r"(?:\*\*)?\s*Step\s+(\d+)\s+\(Action Description\):\s*(?:\*\*)?"
    for match in re.finditer(pattern, steps_text, re.IGNORECASE):
        step = int(match.group(1))
        if step not in nums:
            nums.append(step)
    if not nums:
        for match in re.finditer(r'"step"\s*:\s*(\d+)', steps_text):
            step = int(match.group(1))
            if step not in nums:
                nums.append(step)
    return nums


def compact_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[... trajectory truncated for length ...]\n\n{tail}"


def parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    if not raw.startswith("{"):
        obj = re.search(r"\{.*\}", raw, re.DOTALL)
        if obj:
            raw = obj.group(0)
    raw = raw.replace("\u201c", '"').replace("\u201d", '"')
    raw = raw.replace("\u2018", "'").replace("\u2019", "'")
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return min(ALLOWED_SCORES, key=lambda x: abs(x - score))


def normalize_key_step(value: Any, allowed: list[int]) -> int | None:
    if isinstance(value, list):
        value = value[0] if value else None
    try:
        step = int(value)
    except Exception:
        return None
    return step if step in set(allowed) else None


def normalize_result(obj: dict[str, Any], allowed_steps: list[int]) -> dict[str, Any]:
    key_step_id = normalize_key_step(obj.get("key_step_id"), allowed_steps)
    if key_step_id is None and obj.get("key_steps"):
        key_step_id = normalize_key_step(obj.get("key_steps"), allowed_steps)
    out = {
        "key_step_id": key_step_id,
        "key_step_reason": str(obj.get("key_step_reason", obj.get("reason", ""))).strip(),
    }
    for metric in ("action_relevance", "render_faithfulness", "feedback_uptake"):
        out[metric] = normalize_score(obj.get(metric, 0.0))
        out[f"{metric}_reason"] = str(obj.get(f"{metric}_reason", "")).strip()
    return out


def encode_image(path: Path) -> str:
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    with path.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def create_openai_client():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not set")
    timeout = float(os.environ.get("SEE2THINK_KEY_STEP_METRIC_TIMEOUT", "180"))
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def build_prompt(
    question: str,
    ground_truth: str,
    final_answer: str,
    steps_text: str,
    visual_steps: list[int],
    image_paths: list[Path],
    max_chars: int,
) -> str:
    allowed = ", ".join(str(s) for s in visual_steps) if visual_steps else "none"
    image_order = ", ".join(path.name for path in image_paths) if image_paths else "none"
    return f"""You are a strict process judge for a VAoT-Full visual reasoning trajectory.

Your job has two stages:
1. Choose exactly ONE key visual step from the allowed visual steps.
2. Evaluate ONLY that selected step on three metrics.

Allowed scores for each metric are exactly: 0, 0.5, or 1.
Do not average multiple steps. Do not score the whole trajectory. Score only the selected key step.

Definitions:
- key visual step: the visual action step that is most important for the final reasoning, or the step that best exposes the source of failure.
- Action Relevance:
  1 = the proposed visual action directly targets task-relevant evidence and can help solve the problem.
  0.5 = related but generic, weak, redundant, or only partially targets the relevant evidence.
  0 = irrelevant, decorative, wrong target, or not helpful.
- Render Faithfulness:
  1 = the rendered image faithfully executes the selected action with correct target/location/content.
  0.5 = mostly executes the action but has weak expression, minor offset, partial mismatch, or ambiguity.
  0 = wrong target, wrong operation, misleading render, severe misalignment, artifact, or text conflicts with the action.
- Feedback Uptake:
  1 = later reasoning explicitly uses concrete information visible in the rendered image.
  0.5 = later reasoning loosely references or weakly benefits from the render.
  0 = later reasoning ignores the render, only repeats prior text/action, or would be unchanged without the render.

Important checks:
- If the model wrote its own conclusion into the image and later repeats that text, do not treat it as strong visual uptake.
- If the selected action is only a callout/highlight, it can still score high only when it is truly task-relevant, faithfully rendered, and later consumed.
- Images are attached in chronological order: {image_order}. Usually p0 is the original image and p1/p2/... are rendered images after visual actions.

Question:
{question}

Ground truth/reference answer:
{ground_truth}

Model final answer:
{final_answer}

Allowed visual step numbers:
{allowed}

Trajectory:
{compact_text(steps_text, max_chars)}

Return ONLY this JSON object:
{{
  "key_step_id": 1,
  "key_step_reason": "why this is the single key visual step",
  "action_relevance": 1.0,
  "action_relevance_reason": "reason for this score",
  "render_faithfulness": 0.5,
  "render_faithfulness_reason": "reason for this score",
  "feedback_uptake": 1.0,
  "feedback_uptake_reason": "reason for this score"
}}
"""


def call_judge(
    client: Any,
    args: argparse.Namespace,
    prompt: str,
    image_paths: list[Path],
    allowed_steps: list[int],
) -> tuple[dict[str, Any], str]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_path in image_paths:
        content.append({"type": "image_url", "image_url": {"url": encode_image(image_path)}})
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": args.judge_model,
                "messages": [{"role": "user", "content": content}],
            }
            if args.temperature is not None:
                kwargs["temperature"] = args.temperature
            if attempt == 1:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            return normalize_result(parse_json_object(text), allowed_steps), text
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"judge call failed after {MAX_RETRIES} attempts: {last_err}")


def judge_one(task: dict[str, Any], args: argparse.Namespace, client: Any | None) -> dict[str, Any]:
    data_base = Path(args.data_base)
    output_dir = find_output_dir(Path(args.results_root), args.model, task)
    key = task_key(task)
    if output_dir is None:
        raise FileNotFoundError(f"steps.md not found for {args.model} {key}")
    steps_path = output_dir / "steps.md"
    steps_text = steps_path.read_text(encoding="utf-8", errors="ignore")
    visual_steps = visual_step_numbers(steps_text)
    images = rendered_images(output_dir, args.max_images) if args.include_images else []
    sample = load_sample(data_base, task)
    question = sample_question(sample)
    ground_truth = sample_answer(sample)
    final_answer = extract_final_answer(steps_text)

    if not visual_steps:
        result = {
            "key_step_id": None,
            "key_step_reason": "No visual action step was found in steps.md.",
            "action_relevance": 0.0,
            "action_relevance_reason": "No visual action step exists.",
            "render_faithfulness": 0.0,
            "render_faithfulness_reason": "No rendered visual action exists.",
            "feedback_uptake": 0.0,
            "feedback_uptake_reason": "No rendered visual feedback exists.",
        }
        raw_response = ""
    elif args.dry_run:
        result = {
            "key_step_id": visual_steps[0],
            "key_step_reason": "dry_run",
            "action_relevance": None,
            "action_relevance_reason": "",
            "render_faithfulness": None,
            "render_faithfulness_reason": "",
            "feedback_uptake": None,
            "feedback_uptake_reason": "",
        }
        raw_response = ""
    else:
        if client is None:
            raise RuntimeError("client is required unless --dry-run is set")
        prompt = build_prompt(
            question,
            ground_truth,
            final_answer,
            steps_text,
            visual_steps,
            images,
            args.max_chars,
        )
        result, raw_response = call_judge(client, args, prompt, images, visual_steps)

    return {
        "status": "ok",
        "task_key": key,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "setting": "vaot_full",
        "judge_model": args.judge_model,
        "category": task.get("category", ""),
        "target_task": task.get("target_task", ""),
        "source": task.get("source", ""),
        "relative_source_dir": rel_source_dir(task["path"]),
        "path": task["path"],
        "sample_id": int(task["id"]),
        "output_dir": str(output_dir),
        "steps_md": str(steps_path),
        "render_images": [str(p) for p in images],
        "visual_steps": visual_steps,
        "question": question,
        "ground_truth": ground_truth,
        "final_answer": final_answer,
        **result,
        "raw_response": raw_response,
    }


def flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "status", "task_key", "timestamp", "model", "setting", "judge_model",
        "category", "target_task", "source", "relative_source_dir", "sample_id",
        "output_dir", "steps_md", "visual_steps", "key_step_id", "key_step_reason",
        "action_relevance", "action_relevance_reason",
        "render_faithfulness", "render_faithfulness_reason",
        "feedback_uptake", "feedback_uptake_reason",
        "final_answer",
    ]
    flat = {field: row.get(field) for field in fields}
    flat["visual_steps"] = json.dumps(row.get("visual_steps", []), ensure_ascii=False)
    return flat


def write_csv_results(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(flatten_row({}).keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten_row(row))


def summarize(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "count": len(rows),
        "failure_count": len(failures),
        "metrics": {},
        "by_source": {},
        "key_step_missing_count": sum(1 for r in rows if r.get("key_step_id") is None),
    }
    for metric in ("action_relevance", "render_faithfulness", "feedback_uptake"):
        vals = [float(r[metric]) for r in rows if r.get(metric) is not None]
        summary["metrics"][metric] = {
            "mean": round(sum(vals) / len(vals), 4) if vals else None,
            "count": len(vals),
        }
    for row in rows:
        src = row.get("relative_source_dir", "")
        bucket = summary["by_source"].setdefault(src, {"count": 0, "metrics": {}})
        bucket["count"] += 1
    for src, bucket in summary["by_source"].items():
        for metric in ("action_relevance", "render_faithfulness", "feedback_uptake"):
            vals = [
                float(r[metric])
                for r in rows
                if r.get("relative_source_dir") == src and r.get(metric) is not None
            ]
            bucket["metrics"][metric] = round(sum(vals) / len(vals), 4) if vals else None
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Key-step-only VAoT-Full process judge.")
    parser.add_argument("--tasks", required=True, help="Aligned 600 task JSON list")
    parser.add_argument("--results-root", default="final_results/full")
    parser.add_argument("--model", required=True, help="Evaluated model directory/name")
    parser.add_argument("--data-base", default=".")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output-root", default="eval/results")
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("SEE2THINK_KEY_STEP_METRIC_MODEL", os.environ.get("SEE2THINK_JUDGE_MODEL", "gpt-5.4")),
    )
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-images", type=int, default=6)
    parser.add_argument("--max-chars", type=int, default=24000)
    parser.add_argument("--include-images", dest="include_images", action="store_true", default=True)
    parser.add_argument("--no-images", dest="include_images", action="store_false")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tasks = load_json(Path(args.tasks))
    end = args.end if args.end is not None else len(tasks)
    selected = tasks[args.start:end]
    if args.limit is not None:
        selected = selected[: args.limit]

    out_dir = Path(args.output_root) / args.run_name
    jsonl_path = out_dir / "key_step_metric_judge.jsonl"
    csv_path = out_dir / "key_step_metric_judge.csv"
    summary_path = out_dir / "summary.json"
    failures_path = out_dir / "failures.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for path in (jsonl_path, csv_path, summary_path, failures_path):
            if path.exists():
                path.unlink()

    done = load_existing_keys(jsonl_path)
    todo = [task for task in selected if args.overwrite or task_key(task) not in done]
    print(f"tasks selected={len(selected)} done={len(done)} todo={len(todo)}", flush=True)
    print(f"model={args.model} judge_model={args.judge_model} workers={args.workers}", flush=True)
    print(f"output={out_dir}", flush=True)

    client = None if args.dry_run else create_openai_client()
    failures: list[dict[str, Any]] = []

    def run(task: dict[str, Any]) -> dict[str, Any]:
        return judge_one(task, args, client)

    if args.workers <= 1:
        for idx, task in enumerate(todo, 1):
            key = task_key(task)
            print(f"[{idx}/{len(todo)}] {key}", flush=True)
            try:
                append_jsonl(jsonl_path, run(task))
            except Exception as exc:
                fail = {
                    "status": "failed",
                    "task_key": key,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "error": str(exc),
                    "task": task,
                }
                append_jsonl(failures_path, fail)
                failures.append(fail)
                print(f"FAILED {key}: {exc}", file=sys.stderr, flush=True)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, task): task for task in todo}
            for idx, fut in enumerate(as_completed(futures), 1):
                task = futures[fut]
                key = task_key(task)
                print(f"[{idx}/{len(todo)}] {key}", flush=True)
                try:
                    append_jsonl(jsonl_path, fut.result())
                except Exception as exc:
                    fail = {
                        "status": "failed",
                        "task_key": key,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "error": str(exc),
                        "task": task,
                    }
                    append_jsonl(failures_path, fail)
                    failures.append(fail)
                    print(f"FAILED {key}: {exc}", file=sys.stderr, flush=True)

    all_rows = []
    if jsonl_path.exists():
        with jsonl_path.open("r", encoding="utf-8") as f:
            all_rows = [json.loads(line) for line in f if line.strip()]
    all_failures = []
    if failures_path.exists():
        with failures_path.open("r", encoding="utf-8") as f:
            all_failures = [json.loads(line) for line in f if line.strip()]
    write_csv_results(csv_path, all_rows)
    write_json(summary_path, summarize(all_rows, all_failures))
    print(f"wrote {jsonl_path}", flush=True)
    print(f"wrote {csv_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    if all_failures:
        print(f"failures {len(all_failures)} -> {failures_path}", flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
