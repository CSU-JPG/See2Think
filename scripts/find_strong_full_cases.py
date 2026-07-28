#!/usr/bin/env python3
"""Audit VAoT-Full trajectories for strong visual-dependence cases.

This is a reproducible pre-audit tool. It combines answer correctness, process
judge scores, action JSON heuristics, trajectory text, and image-diff checks.
It does not replace human review; uncertain fields and review notes are emitted
explicitly.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


DATA_PREFIX = "annotation/dataset/data/"

MODEL_CONFIGS = {
    "gpt-5.5": {
        "answer": "neweval/results/answer_gpt55_final1200_vaot_full/answer_judge.jsonl",
        "complete_eval": "neweval/results/complete_eval_gpt55_final1200_vaot_full/complete_process_judge.jsonl",
        "text_answer": "neweval/results/answer_gpt55_text_only_600/answer_judge.jsonl",
        "no_render_answer": "neweval/results/answer_gpt55_no_render_600/answer_judge.jsonl",
    },
    "o3": {
        "answer": "neweval/results/answer_o3_final1200_vaot_full/answer_judge.jsonl",
        "complete_eval": "neweval/results/complete_eval_o3_final1200_vaot_full/complete_process_judge.jsonl",
        "text_answer": "neweval/results/answer_o3_text_only_600/answer_judge.jsonl",
        "no_render_answer": "neweval/results/answer_o3_no_render_600/answer_judge.jsonl",
    },
    "gemini-3.5-flash": {
        "answer": "neweval/results/answer_gemini35flash_final1200_vaot_full/answer_judge.jsonl",
        "complete_eval": "neweval/results/complete_eval_gemini35flash_final1200_vaot_full/complete_process_judge.jsonl",
        "text_answer": "neweval/results/answer_gemini35flash_text_only_600/answer_judge.jsonl",
        "no_render_answer": "neweval/results/answer_gemini35flash_no_render_600/answer_judge.jsonl",
    },
}

ACTION_KEYWORDS_HIGH = {
    "draw_line",
    "line",
    "extend",
    "auxiliary",
    "crop",
    "zoom",
    "magnify",
    "segment",
    "mask",
    "trace",
    "number",
    "count",
    "align",
    "rotate",
    "measure",
    "bbox",
    "box",
    "arrow",
}

CONSUMPTION_PATTERNS = [
    r"rendered image",
    r"rendered view",
    r"new image",
    r"annotated image",
    r"after (?:the )?(?:render|annotation|crop|zoom|line|extension)",
    r"from (?:the )?(?:rendered|annotated|cropped|zoomed) image",
    r"the (?:render|annotation|crop|zoom|line|callout) (?:shows|reveals|confirms|makes)",
    r"we can see",
    r"visible",
    r"highlighted",
    r"numbered",
    r"marked",
    r"labeled",
    r"放大后",
    r"标注后",
    r"渲染",
    r"从图",
    r"图中可以",
]

NEGATIVE_CONSUMPTION_PATTERNS = [
    "visual is not necessary",
    "visual not necessary",
    "no new visual",
    "no additional visual",
    "no visual is needed",
    "visual is unnecessary",
    "not need a new visual",
    "pure algebraic",
    "direct deduction",
]

BAD_TEXT_PATTERNS = [
    "norrazation",
    "normalization",
    "internal parameter",
    "target\": null",
    "undefined",
    "nan",
]

RENDER_BAD_PATTERNS = [
    "wrong",
    "misleading",
    "inconsistent",
    "misaligned",
    "incorrect",
    "missing",
    "conflict",
    "遮挡",
    "错位",
]

ARTIFACT_PATTERNS = ["artifact", "occlusion", "blur", "伪影", "遮挡"]


@dataclass
class StepChunk:
    step: int
    text: str = ""
    action_block: str = ""
    action_json: dict[str, Any] | None = None
    visual_rationale: str = ""
    actions: list[dict[str, Any]] | None = None


def rel_source_dir(data_path: str) -> str:
    p = str(data_path).replace("\\", "/")
    if p.startswith(DATA_PREFIX):
        p = p[len(DATA_PREFIX):]
    if p.endswith("/data.json"):
        p = p[: -len("/data.json")]
    return p


def task_key(task: dict[str, Any]) -> str:
    return f"{rel_source_dir(task['path'])}::{int(task['id'])}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_map(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            key = row.get("task_key")
            if key:
                out[str(key)] = row
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def csv_cell(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def sample_question(sample: dict[str, Any], fallback: str = "") -> str:
    for key in ("question", "modified_question", "problem", "query", "prompt"):
        value = sample.get(key)
        if value:
            return str(value)
    return fallback


def sample_answer(sample: dict[str, Any], fallback: str = "") -> str:
    for key in ("answer", "modified_answer", "ground_truth", "gt_answer", "target"):
        value = sample.get(key)
        if value is not None:
            return str(value)
    return fallback


def output_dir(root: Path, model: str, task: dict[str, Any]) -> Path:
    return root / "final_results" / "full" / model / rel_source_dir(task["path"]) / str(int(task["id"]))


def extract_json_object(text: str) -> dict[str, Any] | None:
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    raw = fence.group(1).strip() if fence else text
    if not raw.strip().startswith("{"):
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        raw = m.group(0)
    raw = raw.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(raw)
    except Exception:
        return None


def parse_steps(steps_text: str) -> list[StepChunk]:
    matches = list(
        re.finditer(
            r"(?:\*\*)?Step\s+(\d+)\s*\((Text|Action Description)\):(?:\*\*)?",
            steps_text,
            flags=re.IGNORECASE,
        )
    )
    chunks: dict[int, StepChunk] = {}
    for i, match in enumerate(matches):
        step = int(match.group(1))
        kind = match.group(2).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(steps_text)
        body = steps_text[start:end].strip()
        chunk = chunks.setdefault(step, StepChunk(step=step, actions=[]))
        if kind == "text":
            chunk.text = body
        else:
            chunk.action_block = body
            action_json = extract_json_object(body)
            chunk.action_json = action_json
            if isinstance(action_json, dict):
                chunk.visual_rationale = str(action_json.get("visual_rationale", "") or "")
                actions = action_json.get("action", [])
                if isinstance(actions, dict):
                    actions = [actions]
                chunk.actions = [a for a in actions if isinstance(a, dict)]
    return [chunks[k] for k in sorted(chunks)]


def action_text(actions: list[dict[str, Any]]) -> str:
    return json.dumps(actions, ensure_ascii=False, sort_keys=True)


def action_types(actions: list[dict[str, Any]]) -> list[str]:
    out = []
    for action in actions:
        parts = [
            str(action.get("type", "")),
            str(action.get("shape", "")),
            str(action.get("operation", "")),
            str(action.get("tool", "")),
        ]
        out.append("/".join(p for p in parts if p).lower())
    return out


def all_action_contents(actions: list[dict[str, Any]]) -> str:
    contents = []
    for action in actions:
        for key in ("content", "label", "text", "caption"):
            if action.get(key):
                contents.append(str(action.get(key)))
    return " ".join(contents)


def token_set(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_°√]+|[\u4e00-\u9fff]+", text) if len(t) > 1}


def overlap_ratio(a: str, b: str) -> float:
    ta = token_set(a)
    tb = token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def subsequent_text(steps: list[StepChunk], step: int) -> str:
    return "\n".join(s.text for s in steps if s.step > step)


def first_consumption_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    for sent in sentences:
        low = sent.lower()
        if any(p in low for p in NEGATIVE_CONSUMPTION_PATTERNS):
            continue
        if any(re.search(p, low) for p in CONSUMPTION_PATTERNS):
            return sent.strip()
    return ""


def image_diff_metrics(original: Path, rendered: Path) -> dict[str, Any]:
    try:
        with Image.open(original) as im0, Image.open(rendered) as im1:
            a = im0.convert("RGB")
            b = im1.convert("RGB")
            if a.size != b.size:
                b = b.resize(a.size)
            diff = ImageChops.difference(a, b)
            stat = ImageStat.Stat(diff)
            mean_diff = sum(stat.mean) / 3.0
            gray = diff.convert("L")
            hist = gray.histogram()
            total = a.size[0] * a.size[1]
            changed = total - sum(hist[:8])
            changed_ratio = changed / total if total else 0.0
            bbox = diff.getbbox()
            bbox_area_ratio = 0.0
            if bbox:
                bbox_area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / total
            return {
                "ok": True,
                "original_size": list(a.size),
                "rendered_size": list(im1.size),
                "mean_diff": round(mean_diff, 3),
                "changed_ratio": round(changed_ratio, 5),
                "bbox_area_ratio": round(bbox_area_ratio, 5),
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def score_original_difficulty(task: dict[str, Any], question: str) -> tuple[int, list[str], bool]:
    rel = rel_source_dir(task["path"])
    target = str(task.get("target_task", ""))
    text = f"{question} {target} {rel}".lower()
    evidence = []
    uncertain = False
    score = 1
    if any(k in text for k in ["geometry", "几何", "clevr", "droid", "intphy", "spatial", "grid", "count", "visible", "diagram", "figure", "shown"]):
        score = 2
        evidence.append("Task/question appears to require reading a diagram, spatial relation, count, or physical/3D state.")
    elif any(k in text for k in ["image", "picture", "图", "visual"]):
        score = 1
        evidence.append("Question references visual content but difficulty is not clearly high from metadata/text.")
        uncertain = True
    else:
        evidence.append("No strong textual sign that the original image contains a hard visual bottleneck.")
        uncertain = True
    return score, evidence, uncertain


def score_action_specificity(actions: list[dict[str, Any]], tags: set[str]) -> tuple[int, list[str]]:
    if not actions:
        return 0, ["No parsed visual action."]
    types = action_types(actions)
    text = " ".join(types + [action_text(actions)]).lower()
    if tags & {"zoom_only", "callout_only"}:
        return 1, [f"Action is limited to {', '.join(sorted(tags & {'zoom_only', 'callout_only'}))}."]
    if any(k in text for k in ACTION_KEYWORDS_HIGH):
        return 2, [f"Action targets specific visual structure: {', '.join(types) or 'parsed action'}."]
    if actions:
        return 1, [f"Action is relevant-looking but ordinary/generic: {', '.join(types) or 'parsed action'}."]
    return 0, ["No task-specific action found."]


def score_render_correctness(process_row: dict[str, Any] | None, diff_metrics: list[dict[str, Any]], tags: set[str]) -> tuple[int, list[str]]:
    judge = (process_row or {}).get("judge", {})
    metric = judge.get("render_faithfulness", {})
    score = metric.get("score")
    reason = str(metric.get("reason", "") or "")
    evidence = []
    if isinstance(score, int):
        evidence.append(f"Process judge render_faithfulness={score}: {reason}")
        out = max(0, min(2, score))
    else:
        out = 1
        evidence.append("No render faithfulness judge score; using image-diff fallback.")
    if not diff_metrics:
        tags.add("render_artifact")
        return 0, evidence + ["No rendered image found."]
    if any(m.get("ok") is False for m in diff_metrics):
        tags.add("render_artifact")
        out = min(out, 0)
        evidence.append("At least one rendered image could not be opened.")
    changed = [m.get("changed_ratio", 0) for m in diff_metrics if m.get("ok")]
    if changed and max(changed) < 0.002:
        out = min(out, 1)
        evidence.append("Image diff is extremely small, suggesting weak visible rendering.")
    if any(p in reason.lower() for p in RENDER_BAD_PATTERNS):
        tags.add("render_target_misaligned")
    if any(p in reason.lower() for p in ARTIFACT_PATTERNS):
        tags.add("render_artifact")
    return out, evidence


def score_novel_evidence(actions: list[dict[str, Any]], before: str, after: str, process_row: dict[str, Any] | None, tags: set[str]) -> tuple[int, list[str], bool]:
    action_content = all_action_contents(actions)
    evidence = []
    uncertain = False
    if action_content and overlap_ratio(action_content, before) > 0.65:
        tags.add("conclusion_written_back")
        evidence.append("Action text overlaps heavily with pre-action reasoning; may write conclusion back onto image.")
        return 0, evidence, False
    if tags & {"callout_only"}:
        evidence.append("Callout-only annotation usually makes existing information easier to see rather than creating new evidence.")
        return 1, evidence, True
    if any(p in after.lower() for p in NEGATIVE_CONSUMPTION_PATTERNS):
        tags.add("no_new_visual_evidence")
        evidence.append("Subsequent reasoning explicitly says no new visual evidence is needed.")
        return 0, evidence, False
    judge = (process_row or {}).get("judge", {})
    uptake = judge.get("feedback_uptake", {}).get("score")
    text = action_text(actions).lower()
    has_structural_action = any(k in text for k in ["draw", "line", "extend", "crop", "segment", "number", "count", "align", "trace", "measure", "bbox", "box"])
    consumption = first_consumption_sentence(after)
    if has_structural_action and uptake == 2 and consumption:
        evidence.append(f"Structural visual action plus explicit later consumption: {consumption}")
        return 2, evidence, False
    if has_structural_action or consumption:
        evidence.append(consumption or "Action is structural, but explicit new evidence is not fully demonstrated.")
        return 1, evidence, True
    tags.add("no_new_visual_evidence")
    evidence.append("No clear new visual fact beyond the original image/text was detected.")
    return 0, evidence, True


def score_consumption(process_row: dict[str, Any] | None, after: str, tags: set[str]) -> tuple[int, list[str]]:
    judge = (process_row or {}).get("judge", {})
    metric = judge.get("feedback_uptake", {})
    score = metric.get("score")
    reason = str(metric.get("reason", "") or "")
    sent = first_consumption_sentence(after)
    evidence = []
    if any(p in after.lower() for p in NEGATIVE_CONSUMPTION_PATTERNS) and not sent:
        tags.add("render_ignored")
        tags.add("visual_action_unnecessary")
        return 0, ["Subsequent reasoning explicitly says visual evidence is not necessary."]
    if isinstance(score, int):
        evidence.append(f"Process judge feedback_uptake={score}: {reason}")
        if score == 2 and sent:
            evidence.append(f"Consumption sentence: {sent}")
            return 2, evidence
        if score == 2:
            return 1, evidence + ["Judge says uptake is high, but no explicit rendered-image sentence was found by text rules."]
        if score == 1:
            return 1, evidence
        tags.add("render_ignored")
        return 0, evidence
    if sent:
        return 1, [f"Detected possible consumption sentence: {sent}"]
    tags.add("render_ignored")
    return 0, ["No downstream rendered-image consumption detected."]


def score_reasoning_impact(
    answer_correct: bool,
    text_answer: dict[str, Any] | None,
    no_render_answer: dict[str, Any] | None,
    novel_score: int,
    uptake_score: int,
) -> tuple[int, list[str], bool]:
    evidence = []
    uncertain = False
    text_correct = text_answer.get("correct") if text_answer else None
    no_render_correct = no_render_answer.get("correct") if no_render_answer else None
    evidence.append(f"Counterfactual answer states: Text-CoT={text_correct}, NoRender={no_render_correct}, Full={answer_correct}.")
    if answer_correct and (text_correct is False or no_render_correct is False) and novel_score == 2 and uptake_score == 2:
        return 2, evidence + ["At least one non-render baseline is wrong while Full is correct."], False
    if answer_correct and novel_score >= 1 and uptake_score >= 1:
        uncertain = text_correct is None and no_render_correct is None
        return 1, evidence + ["Render likely improved reliability, but counterfactual dependence is not decisive."], uncertain
    return 0, evidence + ["Deleting render likely would not change the detected reasoning chain."], True


def classify_grade(scores: dict[str, int], tags: set[str]) -> str:
    total = sum(scores.values())
    if scores["G_final_correctness"] == 0:
        return "REJECT"
    if "render_text_conflict" in tags:
        return "REJECT"
    if scores["C_render_correctness"] == 0 and scores["G_final_correctness"] == 2:
        return "WRONG_RENDER_DIAGNOSTIC"
    if (
        total >= 11
        and scores["D_novel_visual_evidence"] == 2
        and scores["E_downstream_visual_consumption"] == 2
        and scores["F_reasoning_impact"] == 2
        and scores["C_render_correctness"] == 2
        and scores["G_final_correctness"] == 2
    ):
        return "STRONG"
    if 8 <= total <= 10 and scores["C_render_correctness"] > 0:
        return "MID"
    if 5 <= total <= 7:
        return "WEAK"
    return "REJECT"


def audit_one(
    root: Path,
    task: dict[str, Any],
    sample: dict[str, Any],
    model: str,
    answer_row: dict[str, Any],
    process_row: dict[str, Any] | None,
    text_answer: dict[str, Any] | None,
    no_render_answer: dict[str, Any] | None,
) -> dict[str, Any]:
    key = task_key(task)
    out_dir = output_dir(root, model, task)
    steps_path = out_dir / "steps.md"
    q_path = out_dir / "q.md"
    original = out_dir / "p0.png"
    rendered = sorted(out_dir.glob("p[1-9]*.png"), key=lambda p: int(re.findall(r"\d+", p.stem)[0]))
    steps_text = steps_path.read_text(encoding="utf-8", errors="ignore") if steps_path.exists() else ""
    q_text = q_path.read_text(encoding="utf-8", errors="ignore") if q_path.exists() else ""
    steps = parse_steps(steps_text)
    visual_steps = [s for s in steps if s.actions]
    actions = [a for s in visual_steps for a in (s.actions or [])]
    visual_rationales = [s.visual_rationale for s in visual_steps if s.visual_rationale]
    first_visual_step = visual_steps[0].step if visual_steps else None
    before = next((s.text for s in visual_steps if s.step == first_visual_step), "")
    after = subsequent_text(steps, first_visual_step or 0)
    action_types_seen = action_types(actions)
    tags: set[str] = set()
    uncertain_fields: list[str] = []
    all_types = " ".join(action_types_seen).lower()
    if actions and all(("zoom" in t or "crop" in t) for t in action_types_seen):
        tags.add("zoom_only")
    if actions and all(("callout" in t or ("annotate" in t and not any(k in t for k in ["line", "arrow", "box"]))) for t in action_types_seen):
        tags.add("callout_only")
    if not actions:
        tags.add("visual_action_unnecessary")
    if any(p in (steps_text + q_text).lower() for p in BAD_TEXT_PATTERNS):
        tags.add("render_text_conflict")
    answer_correct = answer_row.get("correct") is True
    if not answer_correct:
        tags.add("answer_incorrect")
    diff_metrics = [image_diff_metrics(original, img) for img in rendered] if original.exists() else []

    scores: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    scores["A_original_visual_difficulty"], evidence["A_original_visual_difficulty"], uncertain = score_original_difficulty(task, answer_row.get("question") or sample_question(sample),)
    if uncertain:
        uncertain_fields.append("A_original_visual_difficulty")
    scores["B_action_specificity"], evidence["B_action_specificity"] = score_action_specificity(actions, tags)
    scores["C_render_correctness"], evidence["C_render_correctness"] = score_render_correctness(process_row, diff_metrics, tags)
    scores["D_novel_visual_evidence"], evidence["D_novel_visual_evidence"], uncertain = score_novel_evidence(actions, before, after, process_row, tags)
    if uncertain:
        uncertain_fields.append("D_novel_visual_evidence")
    scores["E_downstream_visual_consumption"], evidence["E_downstream_visual_consumption"] = score_consumption(process_row, after, tags)
    scores["F_reasoning_impact"], evidence["F_reasoning_impact"], uncertain = score_reasoning_impact(
        answer_correct,
        text_answer,
        no_render_answer,
        scores["D_novel_visual_evidence"],
        scores["E_downstream_visual_consumption"],
    )
    if uncertain:
        uncertain_fields.append("F_reasoning_impact")
    scores["G_final_correctness"] = 2 if answer_correct else 0
    evidence["G_final_correctness"] = [f"Answer judge correct={answer_correct}: {answer_row.get('reason', '')}"]
    render_reason = str((process_row or {}).get("judge", {}).get("render_faithfulness", {}).get("reason", "") or "")
    if any(p in render_reason.lower() for p in RENDER_BAD_PATTERNS) and scores["C_render_correctness"] == 0:
        tags.add("render_text_conflict")
    if scores["D_novel_visual_evidence"] == 0:
        tags.add("no_new_visual_evidence")
    if scores["E_downstream_visual_consumption"] == 0:
        tags.add("render_ignored")
    if scores["B_action_specificity"] <= 1 and answer_correct and (text_answer or {}).get("correct") is True and (no_render_answer or {}).get("correct") is True:
        tags.add("visual_action_unnecessary")
    if scores["C_render_correctness"] == 0 and answer_correct:
        tags.add("possible_wrong_render_case")

    total = sum(scores.values())
    grade = classify_grade(scores, tags)
    consumption_sentence = first_consumption_sentence(after)
    key_step = (process_row or {}).get("judge", {}).get("key_step_selection", {})
    return {
        "task_id": f"{model}::{key}",
        "task_key": key,
        "task_family": rel_source_dir(task["path"]),
        "model": model,
        "question": answer_row.get("question") or sample_question(sample),
        "reference_answer": answer_row.get("ground_truth") or sample_answer(sample),
        "model_final_answer": answer_row.get("final_answer", ""),
        "answer_correct": answer_correct,
        "original_image_paths": [str(original)] if original.exists() else [],
        "rendered_image_paths": [str(p) for p in rendered],
        "q_md_path": str(q_path) if q_path.exists() else "",
        "steps_md_path": str(steps_path) if steps_path.exists() else "",
        "output_dir": str(out_dir),
        "visual_actions": actions,
        "visual_action_types": action_types_seen,
        "visual_rationales": visual_rationales,
        "reasoning_before_action": before,
        "reasoning_after_action": after,
        "key_step_selection": key_step,
        "image_diff_metrics": diff_metrics,
        "scores": scores,
        "total_score": total,
        "grade": grade,
        "exclusion_tags": sorted(tags),
        "uncertain_fields": uncertain_fields,
        "evidence": evidence,
        "why_possible_strong": build_possible_strong_reason(scores, evidence, tags),
        "visual_difficulty_summary": "; ".join(evidence.get("A_original_visual_difficulty", [])[:2]),
        "new_visual_evidence_summary": "; ".join(evidence.get("D_novel_visual_evidence", [])[:2]),
        "consumption_sentence": consumption_sentence,
        "delete_render_counterfactual": "; ".join(evidence.get("F_reasoning_impact", [])[:2]),
        "manual_review_concerns": manual_review_concerns(scores, tags, uncertain_fields),
    }


def build_possible_strong_reason(scores: dict[str, int], evidence: dict[str, list[str]], tags: set[str]) -> str:
    if scores["G_final_correctness"] == 0:
        return "Not a strong Full case because the final answer is incorrect."
    parts = []
    if scores["D_novel_visual_evidence"] == 2:
        parts.append("render appears to add nontrivial visual evidence")
    if scores["E_downstream_visual_consumption"] == 2:
        parts.append("subsequent reasoning explicitly consumes the rendered state")
    if scores["F_reasoning_impact"] == 2:
        parts.append("counterfactual baselines suggest the render changed the outcome")
    if not parts:
        parts.append("candidate needs manual review; automatic evidence is weak")
    if tags:
        parts.append(f"tags: {', '.join(sorted(tags))}")
    return "; ".join(parts)


def manual_review_concerns(scores: dict[str, int], tags: set[str], uncertain_fields: list[str]) -> list[str]:
    concerns = []
    if "conclusion_written_back" in tags:
        concerns.append("Check whether the model wrote its own conclusion into the render.")
    if "callout_only" in tags:
        concerns.append("Callout-only action may be decorative; verify actual visual dependency.")
    if scores["D_novel_visual_evidence"] < 2:
        concerns.append("Novel visual evidence is not decisive.")
    if scores["E_downstream_visual_consumption"] < 2:
        concerns.append("Downstream reasoning may not truly read the render.")
    if uncertain_fields:
        concerns.append(f"Uncertain automatic fields: {', '.join(uncertain_fields)}.")
    return concerns


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "task_id",
        "task_key",
        "model",
        "task_family",
        "total_score",
        "grade",
        "answer_correct",
        "novel_visual_evidence",
        "downstream_consumption",
        "reasoning_impact",
        "render_correctness",
        "exclusion_tags",
        "output_dir",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "task_id": row["task_id"],
                    "task_key": row["task_key"],
                    "model": row["model"],
                    "task_family": row["task_family"],
                    "total_score": row["total_score"],
                    "grade": row["grade"],
                    "answer_correct": row["answer_correct"],
                    "novel_visual_evidence": row["scores"]["D_novel_visual_evidence"],
                    "downstream_consumption": row["scores"]["E_downstream_visual_consumption"],
                    "reasoning_impact": row["scores"]["F_reasoning_impact"],
                    "render_correctness": row["scores"]["C_render_correctness"],
                    "exclusion_tags": ";".join(row["exclusion_tags"]),
                    "output_dir": row["output_dir"],
                }
            )


def md_escape(text: Any) -> str:
    return str(text or "").replace("\n", " ").strip()


def write_candidates_md(path: Path, rows: list[dict[str, Any]]) -> None:
    top = sorted(
        [r for r in rows if r["grade"] in {"STRONG", "MID"}],
        key=lambda r: (r["grade"] != "STRONG", -r["total_score"], r["task_id"]),
    )[:30]
    lines = [
        "# Strong VAoT-Full Candidates",
        "",
        "Sorted by grade and total score. These are automatic audit candidates and still require human visual review.",
        "",
    ]
    for i, row in enumerate(top, 1):
        lines += [
            f"## {i}. {row['task_id']}",
            "",
            f"- Path: `{row['output_dir']}`",
            f"- Score: `{row['total_score']}/14`",
            f"- Grade: `{row['grade']}`",
            f"- Why possible strong: {md_escape(row['why_possible_strong'])}",
            f"- Visual difficulty: {md_escape(row['visual_difficulty_summary'])}",
            f"- Rendered evidence: {md_escape(row['new_visual_evidence_summary'])}",
            f"- Downstream consumption: {md_escape(row['consumption_sentence']) or 'not detected'}",
            f"- Delete-render counterfactual: {md_escape(row['delete_render_counterfactual'])}",
            f"- Review concerns: {md_escape('; '.join(row['manual_review_concerns'])) or 'none'}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_wrong_render_md(path: Path, rows: list[dict[str, Any]]) -> None:
    cases = sorted(
        [r for r in rows if r["grade"] == "WRONG_RENDER_DIAGNOSTIC" or "possible_wrong_render_case" in r["exclusion_tags"]],
        key=lambda r: (-r["scores"]["G_final_correctness"], r["task_id"]),
    )
    lines = [
        "# Possible WrongRender Diagnostic Cases",
        "",
        "These are cases where render correctness appears poor but the final answer remains correct. They are useful for diagnosing render ignored / robustness patterns, not for strong Full evidence.",
        "",
    ]
    for row in cases[:100]:
        lines += [
            f"## {row['task_id']}",
            "",
            f"- Path: `{row['output_dir']}`",
            f"- Score: `{row['total_score']}/14`; grade `{row['grade']}`",
            f"- Tags: `{', '.join(row['exclusion_tags'])}`",
            f"- Render evidence: {md_escape('; '.join(row['evidence'].get('C_render_correctness', [])))}",
            f"- Uptake evidence: {md_escape('; '.join(row['evidence'].get('E_downstream_visual_consumption', [])))}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def rel_html_path(from_dir: Path, target: str) -> str:
    try:
        return Path(target).resolve().relative_to(from_dir.resolve()).as_posix()
    except Exception:
        return Path(target).resolve().as_uri()


def write_gallery(path: Path, rows: list[dict[str, Any]]) -> None:
    top = sorted(
        [r for r in rows if r["grade"] in {"STRONG", "MID"}],
        key=lambda r: (r["grade"] != "STRONG", -r["total_score"], r["task_id"]),
    )[:30]
    cards = []
    for row in top:
        images = row["original_image_paths"] + row["rendered_image_paths"]
        image_html = "".join(
            f'<figure><img src="{html.escape(rel_html_path(path.parent, img))}"><figcaption>{html.escape(Path(img).name)}</figcaption></figure>'
            for img in images
        )
        actions = html.escape(json.dumps(row["visual_actions"], ensure_ascii=False, indent=2))
        scores = html.escape(json.dumps(row["scores"], ensure_ascii=False, indent=2))
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(row['task_id'])}</h2>
              <div class="meta">Score {row['total_score']}/14 · {html.escape(row['grade'])} · {html.escape(row['task_family'])}</div>
              <p><strong>Question:</strong> {html.escape(row['question'])}</p>
              <p><strong>Why possible strong:</strong> {html.escape(row['why_possible_strong'])}</p>
              <div class="images">{image_html}</div>
              <div class="grid">
                <div><h3>Before action</h3><pre>{html.escape(row['reasoning_before_action'])}</pre></div>
                <div><h3>After action</h3><pre>{html.escape(row['reasoning_after_action'][:2500])}</pre></div>
              </div>
              <details open><summary>Actions</summary><pre>{actions}</pre></details>
              <details><summary>Scores</summary><pre>{scores}</pre></details>
              <p><strong>Consumption:</strong> {html.escape(row['consumption_sentence'] or 'not detected')}</p>
              <p><strong>Tags:</strong> {html.escape(', '.join(row['exclusion_tags']))}</p>
              <p><strong>Manual review concerns:</strong> {html.escape('; '.join(row['manual_review_concerns']))}</p>
            </section>
            """
        )
    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Strong Full Review Gallery</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#f6f7f9;color:#1f2933;margin:0;padding:20px}}
.card{{background:#fff;border:1px solid #d9dee7;border-radius:8px;padding:16px;margin:0 0 18px}}
.meta{{color:#667085;margin-bottom:10px}} .images{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
figure{{margin:0;border:1px solid #edf0f4;border-radius:6px;background:#fbfcfe;padding:8px}} img{{max-width:100%;max-height:360px;object-fit:contain;display:block;margin:auto}}
figcaption{{color:#667085;font-size:12px;margin-top:6px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#0f172a;color:#e5e7eb;border-radius:6px;padding:10px;max-height:360px;overflow:auto}}
</style></head><body><h1>Strong VAoT-Full Review Gallery</h1>{''.join(cards)}</body></html>"""
    path.write_text(doc, encoding="utf-8")


def write_rule_check(path: Path, rows: list[dict[str, Any]]) -> None:
    candidates = sorted([r for r in rows if r["grade"] in {"STRONG", "MID"}], key=lambda r: -r["total_score"])[:20]
    rejects = [r for r in rows if r["grade"] == "REJECT"][:20]
    payload = {
        "candidate_sample_count": len(candidates),
        "reject_sample_count": len(rejects),
        "candidate_samples": [
            {"task_id": r["task_id"], "score": r["total_score"], "grade": r["grade"], "tags": r["exclusion_tags"], "concerns": r["manual_review_concerns"]}
            for r in candidates
        ],
        "reject_samples": [
            {"task_id": r["task_id"], "score": r["total_score"], "grade": r["grade"], "tags": r["exclusion_tags"], "concerns": r["manual_review_concerns"]}
            for r in rejects
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find strong VAoT-Full cases.")
    parser.add_argument("--root", default=".", help="See2Think project root")
    parser.add_argument("--tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    parser.add_argument("--output-dir", default="outputs/strong_full_audit")
    parser.add_argument("--models", nargs="*", default=list(MODEL_CONFIGS), choices=list(MODEL_CONFIGS))
    parser.add_argument("--limit", type=int, help="Limit tasks per model for debugging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = read_json(root / args.tasks)
    if args.limit:
        tasks = tasks[: args.limit]
    print("Discovered structure:")
    print(f"- task manifest: {root / args.tasks} ({len(tasks)} tasks selected)")
    print(f"- VAoT-Full root: {root / 'final_results' / 'full'}")
    print(f"- output audit dir: {out_dir}")
    for model in args.models:
        cfg = MODEL_CONFIGS[model]
        print(f"- model {model}:")
        print(f"  full outputs: {root / 'final_results' / 'full' / model}")
        print(f"  answer judge: {root / cfg['answer']}")
        print(f"  complete process eval: {root / cfg['complete_eval']}")

    sample_cache: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for model in args.models:
        cfg = MODEL_CONFIGS[model]
        answer_map = read_jsonl_map(root / cfg["answer"])
        process_map = read_jsonl_map(root / cfg["complete_eval"])
        text_map = read_jsonl_map(root / cfg["text_answer"])
        no_render_map = read_jsonl_map(root / cfg["no_render_answer"])
        print(f"Scanning {model}: answer={len(answer_map)} process={len(process_map)}")
        for task in tasks:
            key = task_key(task)
            answer_row = answer_map.get(key)
            if not answer_row:
                continue
            data_path = str(task["path"])
            if data_path not in sample_cache:
                sample_cache[data_path] = read_json(root / data_path)
            sample = sample_cache[data_path][int(task["id"])]
            out = output_dir(root, model, task)
            if not (out / "steps.md").exists():
                continue
            rows.append(
                audit_one(
                    root,
                    task,
                    sample,
                    model,
                    answer_row,
                    process_map.get(key),
                    text_map.get(key),
                    no_render_map.get(key),
                )
            )

    rows.sort(key=lambda r: (-r["total_score"], r["grade"], r["task_id"]))
    write_jsonl(out_dir / "audit_results.jsonl", rows)
    write_summary_csv(out_dir / "audit_summary.csv", rows)
    write_candidates_md(out_dir / "strong_full_candidates.md", rows)
    write_wrong_render_md(out_dir / "wrong_render_candidates.md", rows)
    write_gallery(out_dir / "review_gallery.html", rows)
    write_rule_check(out_dir / "rule_check_sample.json", rows)

    grade_counts = Counter(row["grade"] for row in rows)
    tag_counts = Counter(tag for row in rows for tag in row["exclusion_tags"])
    summary = {
        "scanned_count": len(rows),
        "grade_counts": dict(grade_counts),
        "top_tags": dict(tag_counts.most_common(20)),
        "top_candidates": [
            {
                "task_id": row["task_id"],
                "score": row["total_score"],
                "grade": row["grade"],
                "output_dir": row["output_dir"],
                "why": row["why_possible_strong"],
            }
            for row in sorted(rows, key=lambda r: (-r["total_score"], r["grade"]))[:10]
        ],
    }
    (out_dir / "audit_run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Audit complete:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
