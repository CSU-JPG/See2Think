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


DEFAULT_PROMPT = Path(__file__).with_name("process_judge_prompt.txt")
DATA_PREFIX = "annotation/dataset/data/"
MAX_RETRIES = 3


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


def safe_model_name(model: str) -> str:
    return model.replace(":", "-").replace("/", "_")


def task_key(task: dict[str, Any]) -> str:
    return f"{rel_source_dir(task['path'])}::{int(task['id'])}"


def load_existing_keys(jsonl_path: Path) -> set[str]:
    keys: set[str] = set()
    if not jsonl_path.exists():
        return keys
    with jsonl_path.open("r", encoding="utf-8") as f:
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


def load_sample(data_base: Path, task: dict[str, Any]) -> dict[str, Any]:
    data_path = data_base / task["path"]
    data = load_json(data_path)
    idx = int(task["id"])
    sample = data[idx]
    return sample


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
    marker = "Final Answer:"
    idx = steps_text.lower().rfind(marker.lower())
    if idx >= 0:
        return steps_text[idx + len(marker):].strip()
    return ""


def parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    if not raw.startswith("{"):
        obj = re.search(r"\{.*\}", raw, re.DOTALL)
        if obj:
            raw = obj.group(0)
    raw = raw.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    raw = re.sub(r'\\(?!["\\/bfnrtu])', "", raw)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    if score in {0.0, 0.5, 1.0}:
        return score
    if score in {2.0}:
        return 1.0
    return max(0.0, min(1.0, score))


def normalize_judge_json(obj: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    key_step_id = obj.get("key_step_id")
    try:
        key_step_id = int(key_step_id) if key_step_id is not None else None
    except Exception:
        key_step_id = None
    out["key_step_id"] = key_step_id
    out["key_step_reason"] = str(obj.get("key_step_reason", "")).strip()
    for metric in ("action_relevance", "render_faithfulness", "feedback_uptake"):
        value = obj.get(metric, {})
        if not isinstance(value, dict):
            value = {"score": value, "reason": ""}
        score = clamp_score(value.get("score", 0))
        out[metric] = {
            "score": score,
            "normalized_score": score,
            "reason": str(value.get("reason", "")).strip(),
        }
    failure = str(obj.get("overall_failure_source", "unclear")).strip()
    if failure not in {
        "action_relevance",
        "render_faithfulness",
        "feedback_uptake",
        "none",
        "unclear",
    }:
        failure = "unclear"
    out["overall_failure_source"] = failure
    out["summary"] = str(obj.get("summary", "")).strip()
    return out


def build_process_judge_prompt(sample: dict[str, Any], prompt_template: str) -> str:
    return prompt_template.format(
        question=sample.get("question", ""),
        ground_truth=sample.get("ground_truth", ""),
        final_answer=sample.get("final_answer", ""),
        trajectory_text=sample.get("trajectory_text", ""),
    )


def encode_image(path: Path) -> str:
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    with path.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def rendered_images(output_dir: Path, max_images: int) -> list[Path]:
    images = []
    for path in output_dir.glob("p*.png"):
        m = re.fullmatch(r"p(\d+)\.png", path.name)
        if not m:
            continue
        images.append((int(m.group(1)), path))
    images.sort(key=lambda x: x[0])
    return [p for _, p in images[:max_images]]


def find_output_dir(
    results_root: Path,
    task: dict[str, Any],
    model: str,
    setting: str,
    mode: str,
    aliases: list[str],
) -> Path | None:
    rel = rel_source_dir(task["path"])
    sid = str(int(task["id"]))
    safe_model = safe_model_name(model)
    candidates = []
    for suffix in [setting, *aliases]:
        candidates.append(results_root / rel / f"{mode}_{model}_{suffix}" / sid)
        candidates.append(results_root / rel / f"{mode}_{safe_model}_{suffix}" / sid)
    candidates.append(results_root / rel / f"{mode}_{model}" / sid)
    candidates.append(results_root / rel / f"{mode}_{safe_model}" / sid)
    candidates.append(results_root / rel / sid)
    for cand in candidates:
        if (cand / "steps.md").exists():
            return cand
    rel_root = results_root / rel
    if rel_root.exists():
        patterns = [
            f"{mode}_{model}*",
            f"{mode}_{safe_model}*",
        ]
        for pattern in patterns:
            for parent in sorted(rel_root.glob(pattern)):
                cand = parent / sid
                if (cand / "steps.md").exists():
                    return cand
    return None


def create_openai_client():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not set")
    return OpenAI(api_key=api_key, base_url=base_url)


def call_judge(
    client: Any,
    judge_model: str,
    prompt: str,
    image_paths: list[Path],
    temperature: float,
) -> tuple[dict[str, Any], str]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_path in image_paths:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": encode_image(image_path)},
            }
        )
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs = {
                "model": judge_model,
                "messages": [{"role": "user", "content": content}],
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            parsed = normalize_judge_json(parse_json_object(text))
            return parsed, text
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"judge call failed after {MAX_RETRIES} attempts: {last_err}")


def judge_one(
    task: dict[str, Any],
    args: argparse.Namespace,
    prompt_template: str,
    client: Any | None,
) -> dict[str, Any]:
    data_base = Path(args.data_base)
    output_dir = find_output_dir(
        Path(args.results_root),
        task,
        args.model,
        args.setting,
        args.mode,
        args.setting_alias,
    )
    key = task_key(task)
    if output_dir is None:
        raise FileNotFoundError(f"steps.md not found for {key}")
    steps_path = output_dir / "steps.md"
    trajectory_text = steps_path.read_text(encoding="utf-8", errors="ignore")
    sample = load_sample(data_base, task)
    judge_sample = {
        "question": sample_question(sample),
        "ground_truth": sample_answer(sample),
        "final_answer": extract_final_answer(trajectory_text),
        "trajectory_text": trajectory_text,
    }
    prompt = build_process_judge_prompt(judge_sample, prompt_template)
    images = rendered_images(output_dir, args.max_images) if args.include_images else []
    if args.dry_run:
        result = {
            "action_relevance": {"score": None, "normalized_score": None, "reason": ""},
            "render_faithfulness": {"score": None, "normalized_score": None, "reason": ""},
            "feedback_uptake": {"score": None, "normalized_score": None, "reason": ""},
            "overall_failure_source": "dry_run",
            "summary": "",
        }
        raw_response = ""
    else:
        if client is None:
            raise RuntimeError("client is required when dry_run is false")
        result, raw_response = call_judge(
            client,
            args.judge_model,
            prompt,
            images,
            args.temperature,
        )
    return {
        "status": "ok",
        "task_key": key,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "setting": args.setting,
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
        "question": judge_sample["question"],
        "ground_truth": judge_sample["ground_truth"],
        "final_answer": judge_sample["final_answer"],
        "judge": result,
        "raw_response": raw_response,
    }


def flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    judge = row.get("judge", {})
    flat = {
        "status": row.get("status"),
        "task_key": row.get("task_key"),
        "timestamp": row.get("timestamp"),
        "model": row.get("model"),
        "setting": row.get("setting"),
        "judge_model": row.get("judge_model"),
        "category": row.get("category"),
        "target_task": row.get("target_task"),
        "source": row.get("source"),
        "relative_source_dir": row.get("relative_source_dir"),
        "sample_id": row.get("sample_id"),
        "output_dir": row.get("output_dir"),
        "steps_md": row.get("steps_md"),
        "render_image_count": len(row.get("render_images", [])),
        "final_answer": row.get("final_answer"),
        "overall_failure_source": judge.get("overall_failure_source"),
        "summary": judge.get("summary"),
    }
    for metric in ("action_relevance", "render_faithfulness", "feedback_uptake"):
        value = judge.get(metric, {})
        flat[f"{metric}_score"] = value.get("score")
        flat[f"{metric}_normalized"] = value.get("normalized_score")
        flat[f"{metric}_reason"] = value.get("reason")
    return flat


def write_csv_results(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "status",
        "task_key",
        "timestamp",
        "model",
        "setting",
        "judge_model",
        "category",
        "target_task",
        "source",
        "relative_source_dir",
        "sample_id",
        "output_dir",
        "steps_md",
        "render_image_count",
        "action_relevance_score",
        "action_relevance_normalized",
        "action_relevance_reason",
        "render_faithfulness_score",
        "render_faithfulness_normalized",
        "render_faithfulness_reason",
        "feedback_uptake_score",
        "feedback_uptake_normalized",
        "feedback_uptake_reason",
        "overall_failure_source",
        "summary",
        "final_answer",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten_row(row))


def summarize(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = ("action_relevance", "render_faithfulness", "feedback_uptake")
    summary: dict[str, Any] = {
        "count": len(rows),
        "failure_count": len(failures),
        "metrics": {},
        "overall_failure_source_counts": {},
        "by_source": {},
    }
    for metric in metrics:
        vals = [
            row["judge"][metric]["normalized_score"]
            for row in rows
            if row.get("judge", {}).get(metric, {}).get("normalized_score") is not None
        ]
        summary["metrics"][metric] = {
            "mean_normalized": round(sum(vals) / len(vals), 4) if vals else None,
            "count": len(vals),
        }
    for row in rows:
        src = row["relative_source_dir"]
        summary["by_source"].setdefault(src, {"count": 0, "metrics": {}})
        summary["by_source"][src]["count"] += 1
        failure = row.get("judge", {}).get("overall_failure_source", "unclear")
        summary["overall_failure_source_counts"][failure] = (
            summary["overall_failure_source_counts"].get(failure, 0) + 1
        )
    for src, src_sum in summary["by_source"].items():
        for metric in metrics:
            vals = [
                row["judge"][metric]["normalized_score"]
                for row in rows
                if row["relative_source_dir"] == src
                and row.get("judge", {}).get(metric, {}).get("normalized_score") is not None
            ]
            src_sum["metrics"][metric] = round(sum(vals) / len(vals), 4) if vals else None
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="See2Think process-level VAoT-Full judge")
    parser.add_argument("--tasks", required=True, help="Task JSON list")
    parser.add_argument("--results-root", required=True, help="Root containing model output directories")
    parser.add_argument("--model", required=True, help="Evaluated model name")
    parser.add_argument("--setting", default="vaot_full", help="Evaluated setting name")
    parser.add_argument(
        "--setting-alias",
        action="append",
        default=[],
        help="Additional setting suffix to search, e.g. vaot_full_min1_render",
    )
    parser.add_argument("--mode", default="banana", help="Output mode prefix")
    parser.add_argument("--data-base", default=".", help="Repository/data base")
    parser.add_argument("--judge-model", default=os.environ.get("SEE2THINK_JUDGE_MODEL", "gpt-5"))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT), help="Judge prompt template")
    parser.add_argument("--run-name", required=True, help="Output run name under eval/results")
    parser.add_argument("--output-root", default="eval/results")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-images", type=int, default=6)
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
    jsonl_path = out_dir / "process_judge.jsonl"
    csv_path = out_dir / "process_judge.csv"
    summary_path = out_dir / "summary.json"
    failures_path = out_dir / "failures.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for path in (jsonl_path, csv_path, summary_path, failures_path):
            if path.exists():
                path.unlink()

    prompt_template = Path(args.prompt).read_text(encoding="utf-8")
    done = load_existing_keys(jsonl_path)
    todo = [task for task in selected if args.overwrite or task_key(task) not in done]
    print(f"tasks selected={len(selected)} done={len(done)} todo={len(todo)}", flush=True)
    print(f"output={out_dir}", flush=True)

    client = None if args.dry_run else create_openai_client()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def run(task: dict[str, Any]) -> dict[str, Any]:
        return judge_one(task, args, prompt_template, client)

    if args.workers <= 1:
        for idx, task in enumerate(todo, 1):
            key = task_key(task)
            print(f"[{idx}/{len(todo)}] {key}", flush=True)
            try:
                row = run(task)
                append_jsonl(jsonl_path, row)
                rows.append(row)
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
            futs = {pool.submit(run, task): task for task in todo}
            for idx, fut in enumerate(as_completed(futs), 1):
                task = futs[fut]
                key = task_key(task)
                print(f"[{idx}/{len(todo)}] {key}", flush=True)
                try:
                    row = fut.result()
                    append_jsonl(jsonl_path, row)
                    rows.append(row)
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
