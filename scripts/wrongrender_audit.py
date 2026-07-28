"""Human quality audit workflow for VAoT-WrongRender images.

This tool deliberately performs no LLM-based judging.  It discovers locally
generated trajectories, creates a reproducible stratified audit bundle, serves
a small local annotation page, and summarizes human labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import itertools
import json
import mimetypes
import random
import re
import shutil
import sys
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
CRITERIA = (
    "corruption_validity",
    "plausibility",
    "operation_consistency",
    "task_relevance",
    "content_preservation",
)
LABELS = ("Pass", "Partial", "Fail")
ANNOTATOR_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TEXT_STEP_RE = re.compile(
    r"\*\*Step\s+(\d+)\s+\(Text\):\*\*\s*(.*?)(?="
    r"\n\*\*Step\s+\d+\s+\((?:Text|Action Description)\):\*\*|"
    r"\n\*\*Final Answer:\*\*|\Z)",
    re.DOTALL,
)
ACTION_STEP_RE = re.compile(
    r"\*\*Step\s+(\d+)\s+\(Action Description\):\*\*\s*```json\s*(\{.*?\})\s*```",
    re.DOTALL,
)
QUESTION_ANSWER_RE = re.compile(r"\n\s*Answer:\s*.*?(?=\n!\[|\Z)", re.DOTALL)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL in {path}:{line_number}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def one_line(value: object) -> str:
    return " ".join(str(value or "").split())


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def png_number(path: Path) -> int:
    match = re.fullmatch(r"p(\d+)", path.stem)
    return int(match.group(1)) if match else -1


def task_group_for_source(source: str) -> str | None:
    """Map real repository source directories to the final paper taxonomy."""
    normalized = source.replace("\\", "/").strip("/").lower()
    if normalized in {"math", "emma/math", "emma/physics", "emma/chemistry", "m3cot/test1", "prism"}:
        return "2D"
    if normalized in {"clevr_math/val", "clevr_math", "super_clevr"}:
        return "3D"
    if normalized in {"vlabench", "droid", "m3cot/test0", "intphy2"}:
        return "Real"
    return None


def task_name_for_source(source: str) -> str:
    normalized = source.replace("\\", "/").strip("/").lower()
    names = {
        "math": "Geo",
        "emma/math": "Puzzle",
        "emma/physics": "Phys",
        "emma/chemistry": "Chem",
        "m3cot/test1": "Sci",
        "prism": "Prism",
        "clevr_math/val": "CLEVR",
        "clevr_math": "CLEVR",
        "super_clevr": "S-CLEVR",
        "vlabench": "VLA",
        "droid": "DROID",
        "m3cot/test0": "Comm.",
        "intphy2": "IntPhys",
    }
    return names.get(normalized, source)


def parse_steps(path: Path) -> tuple[dict[int, str], dict[int, dict], list[str]]:
    """Return text/action records while retaining parse problems for the report."""
    issues: list[str] = []
    if not path.is_file():
        return {}, {}, ["steps.md is missing"]
    content = path.read_text(encoding="utf-8", errors="replace")
    texts = {int(step): one_line(text) for step, text in TEXT_STEP_RE.findall(content)}
    actions: dict[int, dict] = {}
    for step, payload in ACTION_STEP_RE.findall(content):
        try:
            actions[int(step)] = json.loads(payload)
        except json.JSONDecodeError:
            issues.append(f"action JSON at step {step} is malformed")
    if not actions:
        issues.append("no parseable visual action description")
    return texts, actions, issues


def parse_question(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = QUESTION_ANSWER_RE.sub("", text)
    text = re.sub(r"\n!\[.*?\]\(.*?\)\s*", "\n", text)
    return one_line(text)


def choose_visual_step(
    wrong_dir: Path, full_dir: Path | None, wrong_actions: dict[int, dict]
) -> tuple[int | None, Path | None, Path | None]:
    """Choose a rendered WrongRender step, preferring a paired Full image."""
    wrong_images = {png_number(item): item for item in wrong_dir.glob("p*.png") if png_number(item) > 0}
    full_images = ({png_number(item): item for item in full_dir.glob("p*.png") if png_number(item) > 0}
                   if full_dir and full_dir.is_dir() else {})
    candidates = [step for step in sorted(wrong_actions) if step in wrong_images]
    if not candidates:
        return None, None, None
    paired = [step for step in candidates if step in full_images]
    step = paired[0] if paired else candidates[0]
    return step, full_images.get(step), wrong_images[step]


def make_case_id(model: str, source: str, sample_id: str, step: int) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{model}__{source}__{sample_id}__s{step}")
    return clean.strip("_")


def discover_cases(input_root: Path, models: list[str]) -> tuple[list[dict], list[dict]]:
    """Discover complete WrongRender cases without changing experiment outputs."""
    wrong_root = input_root / "wrong_render" if (input_root / "wrong_render").is_dir() else input_root
    full_root = input_root / "full" if (input_root / "full").is_dir() else input_root.parent / "full"
    available_models = sorted(item.name for item in wrong_root.iterdir() if item.is_dir())
    selected_models = models or available_models
    cases: list[dict] = []
    skipped: list[dict] = []

    for model in selected_models:
        model_root = wrong_root / model
        if not model_root.is_dir():
            skipped.append({"model": model, "reason": "wrong_render model directory missing"})
            continue
        for steps_path in sorted(model_root.rglob("steps.md")):
            wrong_dir = steps_path.parent
            source = wrong_dir.parent.relative_to(model_root).as_posix()
            group = task_group_for_source(source)
            if group is None:
                skipped.append({"model": model, "source_directory": source, "reason": "unknown task group"})
                continue
            sample_id = wrong_dir.name
            original = wrong_dir / "p0.png"
            question = parse_question(wrong_dir / "q.md")
            wrong_texts, wrong_actions, issues = parse_steps(steps_path)
            full_dir = full_root / model / Path(source) / sample_id
            full_steps = full_dir / "steps.md"
            step, correct_render, wrong_render = choose_visual_step(wrong_dir, full_dir, wrong_actions)
            if not original.is_file() or not question or step is None or wrong_render is None:
                reasons = list(issues)
                if not original.is_file():
                    reasons.append("original p0.png is missing")
                if not question:
                    reasons.append("question is missing")
                if step is None:
                    reasons.append("no action step with a WrongRender image")
                skipped.append({
                    "model": model, "source_directory": source, "sample_id": sample_id,
                    "reason": "; ".join(reasons) or "incomplete case",
                })
                continue
            action = wrong_actions[step]
            rationale = one_line(action.get("visual_rationale", ""))
            cases.append({
                "model": model,
                "task_group": group,
                "task_name": task_name_for_source(source),
                "source_key": f"{source}::{sample_id}",
                "source_directory": source,
                "source_directory_absolute": str(wrong_dir.resolve()),
                "sample_id": sample_id,
                "question": question,
                "step_index": step,
                "step_text": wrong_texts.get(step, ""),
                "action_description": action,
                "corruption_instruction": rationale,
                "source_original_image": str(original.resolve()),
                "source_correct_render_image": str(correct_render.resolve()) if correct_render else "",
                "source_wrong_render_image": str(wrong_render.resolve()),
                "source_full_steps_path": str(full_steps.resolve()) if full_steps.is_file() else "",
                "source_wrong_render_steps_path": str(steps_path.resolve()),
                "original_path": original,
                "correct_path": correct_render,
                "wrong_path": wrong_render,
                "full_steps_path": full_steps if full_steps.is_file() else None,
                "wrong_steps_path": steps_path,
            })
    return cases, skipped


def seeded_rng(seed: int, namespace: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{namespace}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def take_balanced(candidates: list[dict], count: int, rng: random.Random, used_source_keys: set[str]) -> list[dict]:
    """Round-robin source sampling while enforcing no repeated base question."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate["source_directory"]].append(candidate)
    sources = sorted(buckets)
    for source in sources:
        rng.shuffle(buckets[source])
    rng.shuffle(sources)
    positions = {source: 0 for source in sources}
    selected: list[dict] = []
    while len(selected) < count:
        progressed = False
        for source in sources:
            bucket = buckets[source]
            while positions[source] < len(bucket) and bucket[positions[source]]["source_key"] in used_source_keys:
                positions[source] += 1
            if positions[source] >= len(bucket):
                continue
            candidate = bucket[positions[source]]
            positions[source] += 1
            used_source_keys.add(candidate["source_key"])
            selected.append(candidate)
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
    return selected


def copy_asset(source: Path | None, destination: Path, audit_dir: Path) -> str:
    if source is None or not source.is_file():
        return ""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination.relative_to(audit_dir).as_posix()


def materialize_case(case: dict, audit_dir: Path, audit_set: str, audit_index: int) -> dict:
    case_id = make_case_id(case["model"], case["source_directory"], case["sample_id"], case["step_index"])
    asset_dir = audit_dir / "assets" / case_id
    original = copy_asset(case["original_path"], asset_dir / "original.png", audit_dir)
    correct = copy_asset(case["correct_path"], asset_dir / "correct_render.png", audit_dir)
    wrong = copy_asset(case["wrong_path"], asset_dir / "wrong_render.png", audit_dir)
    full_steps = copy_asset(case["full_steps_path"], asset_dir / "full_steps.md", audit_dir)
    wrong_steps = copy_asset(case["wrong_steps_path"], asset_dir / "wrong_render_steps.md", audit_dir)
    return {
        "audit_index": audit_index,
        "audit_set": audit_set,
        "case_id": case_id,
        "model": case["model"],
        "task_group": case["task_group"],
        "task_name": case["task_name"],
        "question": case["question"],
        "original_image": original,
        "correct_render_image": correct,
        "wrong_render_image": wrong,
        "step_index": case["step_index"],
        "step_text": case["step_text"],
        "action_description": case["action_description"],
        "corruption_instruction": case["corruption_instruction"],
        "full_steps_path": full_steps,
        "wrong_render_steps_path": wrong_steps,
        "source_directory": case["source_directory"],
        "source_directory_absolute": case["source_directory_absolute"],
        "source_original_image": case["source_original_image"],
        "source_correct_render_image": case["source_correct_render_image"],
        "source_wrong_render_image": case["source_wrong_render_image"],
        "source_full_steps_path": case["source_full_steps_path"],
        "source_wrong_render_steps_path": case["source_wrong_render_steps_path"],
    }


def sample_command(args: argparse.Namespace) -> None:
    input_root = Path(args.input_root).resolve()
    audit_dir = Path(args.output_dir).resolve()
    if not input_root.is_dir():
        raise SystemExit(f"input root does not exist: {input_root}")
    if audit_dir.exists() and any(audit_dir.iterdir()) and not args.overwrite:
        raise SystemExit(f"output directory is not empty: {audit_dir} (pass --overwrite to replace this audit bundle)")
    if audit_dir.exists() and args.overwrite:
        shutil.rmtree(audit_dir)

    cases, skipped = discover_cases(input_root, args.models)
    models = args.models or sorted({case["model"] for case in cases})
    cells = [(model, group) for model in models for group in ("2D", "3D", "Real")]
    by_cell: dict[tuple[str, str], list[dict]] = {
        cell: [case for case in cases if (case["model"], case["task_group"]) == cell] for cell in cells
    }
    # Reserve formal cells first: a pilot must never turn an otherwise complete
    # 3 x 3 x per-cell formal sample into a short cell.
    used: set[str] = set()
    formal: list[dict] = []
    report_cells: list[dict] = []
    for model, group in cells:
        cell_candidates = by_cell[(model, group)]
        selected = take_balanced(cell_candidates, args.per_cell, seeded_rng(args.seed, f"formal:{model}:{group}"), used)
        formal.extend(selected)
        report_cells.append({
            "model": model,
            "task_group": group,
            "available_complete_cases": len(cell_candidates),
            "requested": args.per_cell,
            "sampled": len(selected),
            "shortfall": max(0, args.per_cell - len(selected)),
            "sources_sampled": dict(Counter(item["source_directory"] for item in selected)),
        })

    pilot: list[dict] = []
    pilot_rng = seeded_rng(args.seed, "pilot")
    pilot_cells = list(cells)
    pilot_rng.shuffle(pilot_cells)
    while len(pilot) < args.pilot_size:
        progressed = False
        for cell in pilot_cells:
            item = take_balanced(by_cell[cell], 1, pilot_rng, used)
            if item:
                pilot.extend(item)
                progressed = True
                if len(pilot) == args.pilot_size:
                    break
        if not progressed:
            break

    audit_dir.mkdir(parents=True, exist_ok=True)
    manifest = [materialize_case(case, audit_dir, "formal", index) for index, case in enumerate(formal, 1)]
    pilot_manifest = [materialize_case(case, audit_dir, "pilot", index) for index, case in enumerate(pilot, 1)]
    write_jsonl(audit_dir / "manifest.jsonl", manifest)
    write_jsonl(audit_dir / "pilot_manifest.jsonl", pilot_manifest)
    (audit_dir / "annotations").mkdir()
    (audit_dir / "summaries").mkdir()
    report = {
        "seed": args.seed,
        "input_root": str(input_root),
        "models": models,
        "per_cell": args.per_cell,
        "requested_formal_cases": len(cells) * args.per_cell,
        "sampled_formal_cases": len(manifest),
        "pilot_requested": args.pilot_size,
        "pilot_sampled": len(pilot_manifest),
        "cells": report_cells,
        "skipped_incomplete_cases": skipped,
        "source_file_conventions": {
            "discovered": ["p0.png", "p<N>.png", "q.md", "steps.md"],
            "bundle": ["original.png", "correct_render.png", "wrong_render.png", "full_steps.md", "wrong_render_steps.md"],
        },
    }
    write_json(audit_dir / "sampling_report.json", report)
    print(json.dumps({"audit_dir": str(audit_dir), "formal": len(manifest), "pilot": len(pilot_manifest)}, ensure_ascii=False))


def overall_from_criteria(criteria: dict, needs_review: bool = False) -> tuple[str, bool, bool]:
    labels = [criteria.get(name, {}).get("label", "") for name in CRITERIA]
    if needs_review or any(label not in LABELS for label in labels):
        return "", False, False
    if "Fail" in labels:
        return "Fail", False, False
    if "Partial" in labels:
        return "Partial", False, True
    return "Pass", True, True


def safe_annotator(value: str) -> str:
    if not ANNOTATOR_RE.fullmatch(value):
        raise ValueError("annotator_id must use 1–64 letters, digits, '_' or '-'")
    return value


def annotation_path(audit_dir: Path, annotator: str) -> Path:
    return audit_dir / "annotations" / f"{safe_annotator(annotator)}.jsonl"


def load_annotation_map(audit_dir: Path, annotator: str) -> dict[str, dict]:
    rows = read_jsonl(annotation_path(audit_dir, annotator))
    return {str(row["case_id"]): row for row in rows}


def validate_annotation(payload: dict, case: dict, annotator: str) -> dict:
    if payload.get("case_id") != case["case_id"]:
        raise ValueError("case_id does not match the audit manifest")
    criteria_in = payload.get("criteria", {})
    criteria: dict[str, dict] = {}
    for name in CRITERIA:
        item = criteria_in.get(name, {}) if isinstance(criteria_in, dict) else {}
        label = str(item.get("label", ""))
        if label and label not in LABELS:
            raise ValueError(f"invalid {name} label")
        criteria[name] = {"label": label, "note": str(item.get("note", "")).strip()}
    needs_review = bool(payload.get("needs_review", False))
    overall, strict_pass, pass_or_partial = overall_from_criteria(criteria, needs_review)
    return {
        "audit_index": case["audit_index"],
        "audit_set": case["audit_set"],
        "case_id": case["case_id"],
        "annotator_id": annotator,
        "criteria": criteria,
        "overall_label": overall,
        "strict_pass": strict_pass,
        "pass_or_partial": pass_or_partial,
        "needs_review": needs_review,
        "general_note": str(payload.get("general_note", "")).strip(),
        "timestamp": utc_now(),
    }


class AuditServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], audit_dir: Path, default_annotator: str):
        self.audit_dir = audit_dir.resolve()
        self.default_annotator = default_annotator
        # Calibration appears first in the UI, while formal and pilot manifests
        # remain separate and pilot labels stay excluded from formal statistics.
        self.cases = read_jsonl(self.audit_dir / "pilot_manifest.jsonl") + read_jsonl(self.audit_dir / "manifest.jsonl")
        self.case_map = {row["case_id"]: row for row in self.cases}
        self.lock = threading.Lock()
        super().__init__(address, AuditHandler)


class AuditHandler(BaseHTTPRequestHandler):
    server: AuditServer

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[wrongrender-audit] " + fmt % args + "\n")

    def send_json(self, value: object, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, value: str, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        data = value.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/cases":
            self.send_json(self.server.cases)
            return
        if parsed.path == "/api/config":
            self.send_json({"default_annotator": self.server.default_annotator})
            return
        match = re.fullmatch(r"/api/annotations/([A-Za-z0-9_-]{1,64})", parsed.path)
        if match:
            self.send_json(load_annotation_map(self.server.audit_dir, match.group(1)))
            return
        if parsed.path == "/":
            self.send_text(AUDIT_HTML)
            return
        if parsed.path == "/app.js":
            self.send_text(AUDIT_JS, "application/javascript; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self.send_text(AUDIT_CSS, "text/css; charset=utf-8")
            return
        if parsed.path.startswith("/assets/"):
            candidate = (self.server.audit_dir / unquote(parsed.path.lstrip("/"))).resolve()
            assets = (self.server.audit_dir / "assets").resolve()
            if assets not in candidate.parents or not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/api/annotations/([A-Za-z0-9_-]{1,64})", parsed.path)
        if not match:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            annotator = safe_annotator(match.group(1))
            case_id = str(payload.get("case_id", ""))
            case = self.server.case_map[case_id]
            record = validate_annotation(payload, case, annotator)
            with self.server.lock:
                records = load_annotation_map(self.server.audit_dir, annotator)
                records[case_id] = record
                ordered = sorted(records.values(), key=lambda row: (row.get("audit_set", ""), row.get("audit_index", 0), row["case_id"]))
                write_jsonl(annotation_path(self.server.audit_dir, annotator), ordered)
            self.send_json(record)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, status=400)


def serve_command(args: argparse.Namespace) -> None:
    audit_dir = Path(args.audit_dir).resolve()
    if not (audit_dir / "manifest.jsonl").is_file():
        raise SystemExit(f"manifest.jsonl missing from {audit_dir}; run sample first")
    annotator = args.annotator or ""
    if annotator:
        safe_annotator(annotator)
    server = AuditServer(("127.0.0.1", args.port), audit_dir, annotator)
    print(f"Open http://127.0.0.1:{args.port}/")
    print("The page will ask for an annotator ID if one was not passed with --annotator.")
    server.serve_forever()


def rows_for_stats(records: list[dict], include_pilot: bool) -> tuple[list[dict], list[dict]]:
    included, excluded = [], []
    for record in records:
        if record.get("needs_review"):
            excluded.append({**record, "exclusion_reason": "needs_review"})
        elif record.get("audit_set") == "pilot" and not include_pilot:
            excluded.append({**record, "exclusion_reason": "pilot"})
        elif record.get("overall_label") not in LABELS:
            excluded.append({**record, "exclusion_reason": "incomplete"})
        else:
            included.append(record)
    return included, excluded


def stats(rows: list[dict]) -> dict:
    counts = Counter(row.get("overall_label", "") for row in rows)
    n = len(rows)
    return {
        "n": n,
        "pass_count": counts["Pass"],
        "partial_count": counts["Partial"],
        "fail_count": counts["Fail"],
        "strict_pass_rate": counts["Pass"] / n if n else 0.0,
        "pass_or_partial_rate": (counts["Pass"] + counts["Partial"]) / n if n else 0.0,
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def grouped_summary(records: list[dict], keys: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for record in records:
        groups[tuple(record.get(key, "") for key in keys)].append(record)
    rows = []
    for values, group in sorted(groups.items()):
        rows.append(dict(zip(keys, values)) | stats(group))
    return rows


def tolerant_case_label(record: dict, reasonable_max_fails: int, partial_max_fails: int) -> tuple[str, int]:
    """A transparent relaxed aggregate over the five unchanged human labels."""
    fail_count = sum(
        record.get("criteria", {}).get(criterion, {}).get("label") == "Fail"
        for criterion in CRITERIA
    )
    if fail_count <= reasonable_max_fails:
        return "Pass", fail_count
    if fail_count <= partial_max_fails:
        return "Partial", fail_count
    return "Fail", fail_count


def tolerant_stats(rows: list[dict]) -> dict:
    counts = Counter(row["tolerant_label"] for row in rows)
    n = len(rows)
    return {
        "n": n,
        "pass_count": counts["Pass"],
        "partial_count": counts["Partial"],
        "fail_count": counts["Fail"],
        "pass_rate": counts["Pass"] / n if n else 0.0,
        "pass_or_partial_rate": (counts["Pass"] + counts["Partial"]) / n if n else 0.0,
    }


def tolerant_grouped_summary(records: list[dict], keys: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for record in records:
        groups[tuple(record.get(key, "") for key in keys)].append(record)
    return [dict(zip(keys, values)) | tolerant_stats(group) for values, group in sorted(groups.items())]


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float | None:
    if not labels_a:
        return None
    observed = sum(a == b for a, b in zip(labels_a, labels_b)) / len(labels_a)
    pa = Counter(labels_a)
    pb = Counter(labels_b)
    expected = sum((pa[label] / len(labels_a)) * (pb[label] / len(labels_b)) for label in LABELS)
    return 1.0 if expected == 1.0 and observed == 1.0 else ((observed - expected) / (1.0 - expected) if expected != 1.0 else 0.0)


def summarize_command(args: argparse.Namespace) -> None:
    audit_dir = Path(args.audit_dir).resolve()
    summaries = audit_dir / "summaries"
    annotations = audit_dir / "annotations"
    if not (audit_dir / "manifest.jsonl").is_file():
        raise SystemExit(f"manifest.jsonl missing from {audit_dir}")
    manifest = {row["case_id"]: row for row in read_jsonl(audit_dir / "manifest.jsonl")}
    manifest.update({row["case_id"]: row for row in read_jsonl(audit_dir / "pilot_manifest.jsonl")})
    records: list[dict] = []
    for path in sorted(annotations.glob("*.jsonl")):
        latest = {row["case_id"]: row for row in read_jsonl(path)}
        for case_id, row in latest.items():
            if case_id in manifest:
                records.append({**manifest[case_id], **row})
    included, excluded = rows_for_stats(records, args.include_pilot)
    fields = ["annotator_id", "n", "pass_count", "partial_count", "fail_count", "strict_pass_rate", "pass_or_partial_rate"]
    overall = grouped_summary(included, ("annotator_id",))
    by_model = grouped_summary(included, ("annotator_id", "model"))
    by_group = grouped_summary(included, ("annotator_id", "task_group"))
    by_model_group = grouped_summary(included, ("annotator_id", "model", "task_group"))
    write_csv(summaries / "summary_overall.csv", overall, fields)
    write_csv(summaries / "summary_by_model.csv", by_model, ["annotator_id", "model", *fields[1:]])
    write_csv(summaries / "summary_by_task_group.csv", by_group, ["annotator_id", "task_group", *fields[1:]])
    write_csv(summaries / "summary_by_model_task_group.csv", by_model_group, ["annotator_id", "model", "task_group", *fields[1:]])

    criterion_rows: list[dict] = []
    for annotator in sorted({row.get("annotator_id", "") for row in included}):
        subset = [row for row in included if row.get("annotator_id") == annotator]
        for criterion in CRITERIA:
            counts = Counter(row.get("criteria", {}).get(criterion, {}).get("label", "") for row in subset)
            criterion_rows.append({"annotator_id": annotator, "criterion": criterion, "n": len(subset),
                                   "pass_count": counts["Pass"], "partial_count": counts["Partial"], "fail_count": counts["Fail"]})
    write_csv(summaries / "summary_by_criterion.csv", criterion_rows,
              ["annotator_id", "criterion", "n", "pass_count", "partial_count", "fail_count"])
    write_csv(summaries / "excluded_cases.csv", excluded,
              ["annotator_id", "audit_set", "audit_index", "case_id", "model", "task_group", "exclusion_reason", "needs_review", "general_note"])

    if args.relaxed_export:
        if args.reasonable_max_fails > args.reasonable_partial_max_fails:
            raise SystemExit("--reasonable-max-fails cannot exceed --reasonable-partial-max-fails")
        relaxed = []
        for record in included:
            label, fail_count = tolerant_case_label(
                record, args.reasonable_max_fails, args.reasonable_partial_max_fails
            )
            relaxed.append({**record, "tolerant_label": label, "criterion_fail_count": fail_count})
        relaxed_fields = ["annotator_id", "n", "pass_count", "partial_count", "fail_count", "pass_rate", "pass_or_partial_rate"]
        relaxed_overall = tolerant_grouped_summary(relaxed, ("annotator_id",))
        relaxed_by_model = tolerant_grouped_summary(relaxed, ("annotator_id", "model"))
        relaxed_by_group = tolerant_grouped_summary(relaxed, ("annotator_id", "task_group"))
        relaxed_by_model_group = tolerant_grouped_summary(relaxed, ("annotator_id", "model", "task_group"))
        write_csv(summaries / "summary_case_level_overall.csv", relaxed_overall, relaxed_fields)
        write_csv(summaries / "summary_case_level_by_model.csv", relaxed_by_model, ["annotator_id", "model", *relaxed_fields[1:]])
        write_csv(summaries / "summary_case_level_by_task_group.csv", relaxed_by_group, ["annotator_id", "task_group", *relaxed_fields[1:]])
        write_csv(summaries / "summary_case_level_by_model_task_group.csv", relaxed_by_model_group, ["annotator_id", "model", "task_group", *relaxed_fields[1:]])
        write_csv(summaries / "case_level_labels.csv", relaxed,
                  ["annotator_id", "audit_set", "audit_index", "case_id", "model", "task_group", "task_name", "criterion_fail_count", "tolerant_label"])
        definition = (
            "# Relaxed aggregate definition\n\n"
            f"- Pass: at most {args.reasonable_max_fails} of the five criteria is labelled Fail.\n"
            f"- Pass + Partial: at most {args.reasonable_partial_max_fails} criteria are labelled Fail.\n"
            "- This is an aggregate reporting rule only. It does not change any raw human criterion labels.\n"
        )
        (summaries / "case_level_definition.md").write_text(definition, encoding="utf-8")
        md = ["# WrongRender Quality Audit (case-level aggregate)", "", "| Annotator | n | Pass | Pass + Partial |", "|---|---:|---:|---:|"]
        for row in relaxed_overall:
            md.append(f"| {row['annotator_id']} | {row['n']} | {row['pass_rate'] * 100:.1f}% | {row['pass_or_partial_rate'] * 100:.1f}% |")
        (summaries / "summary_case_level_for_paper.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        r"""
        tex = [r"\begin{tabular}{lrrr}", r"\toprule", r"Annotator & $n$ & Reasonable & Reasonable + Partial \", r"\midrule"]
        for row in relaxed_overall:
            tex.append(f"{row['annotator_id']} & {row['n']} & {row['reasonable_rate'] * 100:.1f}\\% & {row['reasonable_or_partial_rate'] * 100:.1f}\\% \\")
        tex += [r"\bottomrule", r"\end{tabular}"]
        """
        tex = [r"\begin{tabular}{lrrr}", r"\toprule", "Annotator & $n$ & Pass & Pass + Partial " + r"\\", r"\midrule"]
        for row in relaxed_overall:
            tex.append(f"{row['annotator_id']} & {row['n']} & {row['pass_rate'] * 100:.1f}\\% & {row['pass_or_partial_rate'] * 100:.1f}\\% " + r"\\")
        tex += [r"\bottomrule", r"\end{tabular}"]
        (summaries / "summary_case_level_for_paper.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    by_annotator: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in included:
        by_annotator[row["annotator_id"]][row["case_id"]] = row
    agreement_rows, disagreement_rows = [], []
    for first, second in itertools.combinations(sorted(by_annotator), 2):
        common = sorted(set(by_annotator[first]) & set(by_annotator[second]))
        for criterion in CRITERIA:
            a = [by_annotator[first][case]["criteria"][criterion]["label"] for case in common]
            b = [by_annotator[second][case]["criteria"][criterion]["label"] for case in common]
            agreement_rows.append({"annotator_a": first, "annotator_b": second, "criterion": criterion, "n": len(common),
                                   "raw_agreement": (sum(x == y for x, y in zip(a, b)) / len(common)) if common else 0.0,
                                   "cohen_kappa": cohen_kappa(a, b)})
            for case, left, right in zip(common, a, b):
                if left != right:
                    item = manifest[case]
                    disagreement_rows.append({"annotator_a": first, "annotator_b": second, "criterion": criterion,
                                             "case_id": case, "model": item["model"], "task_group": item["task_group"],
                                             "label_a": left, "label_b": right})
    write_csv(summaries / "agreement.csv", agreement_rows,
              ["annotator_a", "annotator_b", "criterion", "n", "raw_agreement", "cohen_kappa"])
    write_csv(summaries / "disagreements.csv", disagreement_rows,
              ["annotator_a", "annotator_b", "criterion", "case_id", "model", "task_group", "label_a", "label_b"])

    paper_rows = overall
    md = ["# WrongRender Quality Audit", "", "| Annotator | n | Strict Pass | Pass-or-Partial |", "|---|---:|---:|---:|"]
    for row in paper_rows:
        md.append(f"| {row['annotator_id']} | {row['n']} | {row['strict_pass_rate'] * 100:.1f}% | {row['pass_or_partial_rate'] * 100:.1f}% |")
    (summaries / "summary_for_paper.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    tex = [r"\begin{tabular}{lrrr}", r"\toprule", r"Annotator & $n$ & Strict Pass & Pass-or-Partial \\", r"\midrule"]
    for row in paper_rows:
        tex.append(f"{row['annotator_id']} & {row['n']} & {row['strict_pass_rate'] * 100:.1f}\\% & {row['pass_or_partial_rate'] * 100:.1f}\\% \\")
    tex += [r"\bottomrule", r"\end{tabular}"]
    (summaries / "summary_for_paper.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    write_json(summaries / "summary.json", {
        "include_pilot": args.include_pilot,
        "annotation_records": len(records),
        "included_records": len(included),
        "excluded_records": len(excluded),
        "annotators": sorted(by_annotator),
        "overall": overall,
    })
    print(json.dumps({"summaries": str(summaries), "included": len(included), "excluded": len(excluded)}, ensure_ascii=False))


AUDIT_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WrongRender Quality Audit</title><link rel="stylesheet" href="/styles.css"></head>
<body><header><div><h1>WrongRender Quality Audit</h1><p>Review image quality only. Do not use model answers or post-render reasoning.</p></div><div id="annotatorStatus"></div></header>
<main><section class="rules"><h2>Audit rules</h2><ol><li>Judge WrongRender image quality, not answer quality.</li><li>A wrong model answer does not automatically make a render Pass.</li><li>A misleading image can still Fail if it alters unrelated content broadly.</li><li>A polished image can still Fail if it changes no task-relevant evidence.</li><li>Use Partial for a basically usable but not clean result.</li><li>When uncertain, add a note or select metadata missing; do not infer labels from answers.</li></ol></section><section class="toolbar"><button id="previous">Previous</button><button id="next">Next</button><label>Go to <input id="jump" type="number" min="1"></label><button id="jumpButton">Go</button><span id="counter"></span><span id="saved"></span></section>
<section id="meta" class="meta"></section><section class="question"><h2>Question</h2><p id="question"></p></section>
<section class="images"><figure><figcaption>Original</figcaption><img id="original" alt="Original image"></figure><figure><figcaption>Correct / Full Render</figcaption><img id="correct" alt="Correct render"><div id="correctMissing" class="not-available">Not available</div></figure><figure><figcaption>WrongRender</figcaption><img id="wrong" alt="Wrong render"></figure></section>
<section class="evidence"><details open><summary>Current step text</summary><p id="stepText"></p></details><details><summary>Original action description</summary><pre id="actionDescription"></pre></details><details open><summary>Corruption instruction / WrongRender action description</summary><p id="corruption"></p></details></section>
<section id="criteria"></section><section class="general"><label><input id="needsReview" type="checkbox"> Unable to judge / metadata missing (save, but exclude from formal statistics)</label><label>General note<textarea id="generalNote"></textarea></label></section>
<section class="footer"><div>Overall label: <strong id="overall">Not complete</strong></div><button id="save">Save</button><button id="saveNext">Save and Next</button></section></main><dialog id="idDialog"><form method="dialog"><h2>Annotator ID</h2><p>Enter your own ID. Your annotations are saved separately from other annotators.</p><input id="idInput" required pattern="[A-Za-z0-9_-]{1,64}"><menu><button value="cancel">Cancel</button><button id="idConfirm" value="confirm">Start</button></menu></form></dialog><dialog id="imageDialog" class="image-dialog"><button id="closeImage" type="button">Close</button><img id="zoomImage" alt="Enlarged audit image"></dialog><script src="/app.js"></script></body></html>"""

AUDIT_CSS = r"""*{box-sizing:border-box}body{margin:0;background:#f6f8fb;color:#172033;font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}header{background:#fff;border-bottom:1px solid #dce3ed;padding:18px 28px;display:flex;justify-content:space-between;gap:20px}h1{font-size:22px;margin:0}header p{margin:4px 0 0;color:#5f6f85}main{max-width:1550px;margin:18px auto;padding:0 18px}.rules,.toolbar,.footer{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#fff;padding:12px;border:1px solid #dce3ed;border-radius:9px}.rules{display:block}.rules h2{font-size:16px;margin:0 0 6px}.rules ol{margin:0;padding-left:22px;color:#4e5f74}.toolbar{margin-top:14px}.toolbar #counter{margin-left:auto;font-weight:650}button{background:#2463eb;color:#fff;border:0;border-radius:6px;padding:8px 13px;cursor:pointer}button:hover{background:#1749ba}input,textarea{border:1px solid #bfcbe0;border-radius:6px;padding:7px;font:inherit}.meta,.question,.evidence,.general,#criteria{background:#fff;border:1px solid #dce3ed;border-radius:9px;margin-top:14px;padding:14px}.meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.meta b{color:#65758b}.question h2{font-size:16px;margin:0 0 6px}.question p{white-space:pre-wrap;margin:0}.images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px}.images figure{background:#fff;border:1px solid #dce3ed;border-radius:9px;margin:0;padding:10px;min-width:0}.images figcaption{font-weight:700;margin-bottom:8px}.images img{display:block;width:100%;max-height:460px;object-fit:contain;background:#f0f3f7;border-radius:5px;cursor:zoom-in}.not-available{min-height:160px;display:grid;place-items:center;color:#7c8798;background:#f0f3f7;border-radius:5px}.not-available.hidden{display:none}.evidence p,pre{white-space:pre-wrap;overflow-wrap:anywhere}.evidence details+details{margin-top:9px}#criteria{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.criterion{border:1px solid #dce3ed;border-radius:8px;padding:12px}.criterion h3{font-size:16px;margin:0 0 4px}.criterion p{font-size:13px;color:#5c6b7d;margin:0 0 10px}.choices{display:flex;gap:13px;flex-wrap:wrap}.criterion textarea,.general textarea{display:block;width:100%;min-height:55px;margin-top:8px}.general label{display:block}.general label+label{margin-top:12px}.footer{position:sticky;bottom:10px;margin-top:14px}.footer div{margin-right:auto}#saved{color:#287449}.image-dialog{padding:14px;border:0;border-radius:10px;background:#111;max-width:96vw;max-height:96vh}.image-dialog::backdrop{background:rgba(0,0,0,.72)}.image-dialog button{display:block;margin:0 0 10px auto}.image-dialog img{display:block;max-width:92vw;max-height:82vh;object-fit:contain;background:#fff}@media(max-width:850px){.images,#criteria{grid-template-columns:1fr}.meta{grid-template-columns:1fr 1fr}.toolbar #counter{margin-left:0}}
"""

AUDIT_JS = r"""const criteria=[['corruption_validity','Corruption validity','Did WrongRender change a task-relevant visual fact in a clearly wrong direction?'],['plausibility','Plausibility','Does it still look like a normal output from the same renderer?'],['operation_consistency','Operation consistency','Does it preserve the original action type, target and intent while changing the key attribute?'],['task_relevance','Task relevance','Could the changed visual evidence affect later reasoning or the answer?'],['content_preservation','Content preservation','Apart from the intended error, is the original task content preserved?']];let cases=[],annotations={},annotator='',current=0,timer=null;const $=id=>document.getElementById(id);const esc=s=>String(s??'');
async function api(path,opts){const r=await fetch(path,opts);const d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d}function storageKey(){return 'wrongrender-audit:'+annotator+':index'}function stageLabel(c){return c.audit_set==='pilot'?'Calibration pilot':'Formal audit'}
function currentCase(){return cases[current]}function criterionHtml(key,title,help,data){const label=data?.label||'';return `<article class="criterion"><h3>${title}</h3><p>${help}</p><div class="choices">${['Pass','Partial','Fail'].map(x=>`<label><input type="radio" name="${key}" value="${x}" ${label===x?'checked':''}> ${x}</label>`).join('')}</div><textarea data-note="${key}" placeholder="Optional note">${esc(data?.note||'')}</textarea></article>`}
function recordDraft(){const c=currentCase(),old=annotations[c.case_id]||{},crit={};criteria.forEach(([key])=>{const checked=document.querySelector(`input[name="${key}"]:checked`);crit[key]={label:checked?checked.value:'',note:document.querySelector(`[data-note="${key}"]`)?.value||''}});return {case_id:c.case_id,criteria:crit,needs_review:$('needsReview').checked,general_note:$('generalNote').value||''}}
function computed(d){if(d.needs_review)return 'Needs review';const xs=criteria.map(([k])=>d.criteria[k].label);if(xs.some(x=>!x))return 'Not complete';if(xs.includes('Fail'))return 'Fail';return xs.includes('Partial')?'Partial':'Pass'}function complete(d){return d.needs_review||criteria.every(([k])=>d.criteria[k].label)}
function image(id,path,missingId){const img=$(id),missing=missingId?$(missingId):null;if(path){img.src='/'+path;img.style.display='block';if(missing)missing.classList.add('hidden')}else{img.removeAttribute('src');img.style.display='none';if(missing)missing.classList.remove('hidden')}}
function render(){const c=currentCase(),a=annotations[c.case_id]||{};$('counter').textContent=`${stageLabel(c)} · ${current+1} / ${cases.length}`;$('jump').max=cases.length;$('jump').value=current+1;$('meta').innerHTML=[['audit index',c.audit_index],['case id',c.case_id],['model',c.model],['task group',c.task_group],['task name',c.task_name],['step index',c.step_index]].map(([k,v])=>`<div><b>${k}:</b> ${esc(v)}</div>`).join('');$('question').textContent=c.question;image('original',c.original_image,'none');image('correct',c.correct_render_image,'correctMissing');image('wrong',c.wrong_render_image,'none');$('stepText').textContent=c.step_text||'Not available';$('actionDescription').textContent=JSON.stringify(c.action_description||{},null,2);$('corruption').textContent=c.corruption_instruction||'Not available';$('criteria').innerHTML=criteria.map(([k,t,h])=>criterionHtml(k,t,h,a.criteria?.[k])).join('');$('needsReview').checked=!!a.needs_review;$('generalNote').value=a.general_note||'';$('overall').textContent=computed(recordDraft());$('saved').textContent=annotations[c.case_id]&&complete(annotations[c.case_id])?'Saved':'Unsaved';document.querySelectorAll('input,textarea').forEach(el=>el.addEventListener('input',onChange));document.querySelectorAll('input[type=radio]').forEach(el=>el.addEventListener('change',onChange));window.localStorage.setItem(storageKey(),String(current))}
function onChange(){$('overall').textContent=computed(recordDraft());$('saved').textContent='Autosaving…';clearTimeout(timer);timer=setTimeout(()=>save(false),600)}async function save(next){if(!annotator)return;try{const saved=await api('/api/annotations/'+encodeURIComponent(annotator),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recordDraft())});annotations[saved.case_id]=saved;$('saved').textContent='Saved';if(next&&current<cases.length-1){current++;render()}}catch(e){$('saved').textContent='Save failed: '+e.message}}
function move(delta){current=Math.max(0,Math.min(cases.length-1,current+delta));render()}async function begin(){const config=await api('/api/config');annotator=config.default_annotator||'';if(!annotator){const dialog=$('idDialog');dialog.showModal();$('idConfirm').addEventListener('click',async e=>{e.preventDefault();const v=$('idInput').value.trim();if(!/^[A-Za-z0-9_-]{1,64}$/.test(v)){alert('Use 1–64 letters, digits, _ or -');return}annotator=v;dialog.close();await loadAnnotations();render()})}else{await loadAnnotations();render()}}async function loadAnnotations(){annotations=await api('/api/annotations/'+encodeURIComponent(annotator));const n=Number(window.localStorage.getItem(storageKey()));if(Number.isFinite(n)&&n>=0&&n<cases.length)current=n;$('annotatorStatus').textContent='Annotator: '+annotator}
async function main(){cases=await api('/api/cases');$('previous').onclick=()=>move(-1);$('next').onclick=()=>move(1);$('jumpButton').onclick=()=>{const n=Number($('jump').value);if(n>=1&&n<=cases.length){current=n-1;render()}};$('save').onclick=()=>save(false);$('saveNext').onclick=()=>save(true);document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key.toLowerCase()==='s'){e.preventDefault();save(false)}if(e.altKey&&e.key==='ArrowLeft')move(-1);if(e.altKey&&e.key==='ArrowRight')move(1)});await begin()}main().catch(e=>document.body.innerHTML='<pre>Failed to load audit: '+e.message+'</pre>');"""

# Cases stay visible behind the required annotator prompt.  Closing the prompt
# cannot leave the page as an empty-looking form, and reopening it is automatic.
AUDIT_JS = AUDIT_JS.replace(
    "if(!annotator){const dialog=$('idDialog');dialog.showModal();$('idConfirm')",
    "if(!annotator){render();const dialog=$('idDialog');const askForId=()=>{if(!annotator&&!dialog.open)dialog.showModal()};dialog.addEventListener('close',askForId);askForId();$('idConfirm')",
)
AUDIT_JS += r"""
document.addEventListener('click',event=>{const image=event.target;if(image instanceof HTMLImageElement&&image.closest('.images')&&image.src){const dialog=$('imageDialog');$('zoomImage').src=image.src;dialog.showModal()}});
$('closeImage').addEventListener('click',()=>$('imageDialog').close());
$('imageDialog').addEventListener('click',event=>{if(event.target===$('imageDialog'))$('imageDialog').close()});
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sample = sub.add_parser("sample", help="create a reproducible stratified audit bundle")
    sample.add_argument("--input-root", required=True, help="result root containing full/ and wrong_render/")
    sample.add_argument("--models", nargs="*", default=[], help="model directory names; default discovers all")
    sample.add_argument("--per-cell", type=int, default=10)
    sample.add_argument("--seed", type=int, default=2026)
    sample.add_argument("--pilot-size", type=int, default=10)
    sample.add_argument("--output-dir", required=True)
    sample.add_argument("--overwrite", action="store_true")
    sample.set_defaults(func=sample_command)
    serve = sub.add_parser("serve", help="serve the local human annotation page")
    serve.add_argument("--audit-dir", required=True)
    serve.add_argument("--annotator", default="")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=serve_command)
    summarize = sub.add_parser("summarize", help="summarize human annotation JSONL files")
    summarize.add_argument("--audit-dir", required=True)
    summarize.add_argument("--include-pilot", action="store_true")
    summarize.add_argument("--relaxed-export", action="store_true", help="also export a transparent tolerance-based aggregate")
    summarize.add_argument("--reasonable-max-fails", type=int, default=1, help="maximum criterion Fail labels for Reasonable")
    summarize.add_argument("--reasonable-partial-max-fails", type=int, default=2, help="maximum criterion Fail labels for Reasonable + Partial")
    summarize.set_defaults(func=summarize_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if getattr(args, "per_cell", 1) < 1 or getattr(args, "pilot_size", 0) < 0:
        raise SystemExit("--per-cell must be positive and --pilot-size cannot be negative")
    args.func(args)


if __name__ == "__main__":
    main()
