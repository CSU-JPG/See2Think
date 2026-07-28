"""Select and export paper-ready Appendix E qualitative examples from final 1,200 runs."""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200" / "complete_evaluations"
SEMANTIC = ROOT / "outputs" / "analysis_split_and_merged_1200" / "merged_1200" / "semantic_answer_change_1200"
OUT = ROOT / "outputs" / "appendix_e_qualitative_examples_1200"
KATEX_ASSETS = ROOT / "assets" / "katex"
MODELS = (
    ("gpt-5.5", "gpt55", "gpt55_full_vs_wrongrender_1200"),
    ("o3", "o3", "o3_full_vs_wrongrender_1200"),
    ("gemini-3.5-flash", "gemini35flash", "gemini35flash_full_vs_wrongrender_1200"),
)
CATEGORIES = ("2D", "3D", "Real")
PREFERRED = {
    ("E1_success", "2D"): "gpt-5.5", ("E1_diagnostic", "2D"): "o3",
    ("E1_success", "3D"): "o3", ("E1_diagnostic", "3D"): "gemini-3.5-flash",
    ("E1_success", "Real"): "gemini-3.5-flash", ("E1_diagnostic", "Real"): "gpt-5.5",
    ("E2_wrongrender", "2D"): "gemini-3.5-flash", ("E2_wrongrender", "3D"): "o3", ("E2_wrongrender", "Real"): "gemini-3.5-flash",
}

# Hand-picked after visual inspection.  The 2D case uses the same folding-axis
# intervention in both conditions and has coherent evidence-to-answer changes.
FIXED_E2_SELECTIONS = {
    "2D": ("gpt-5.5", "emma/physics::45"),
}


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def map_rows(rows: list[dict]) -> dict[str, dict]:
    return {str(row["task_key"]): row for row in rows}


def safe_name(value: str) -> str:
    return value.replace("/", "__").replace("::", "_").replace(" ", "_")


def candidate_wrong_dir(model: str, source: str, sample_id: int, split: str) -> Path:
    root = ROOT / ("final_results" if split == "old_600" else "final_results_1200")
    return root / "wrong_render" / model / source / str(sample_id)


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def choose(candidates: list[dict], preferred_model: str, rank) -> dict:
    preferred = [row for row in candidates if row["model"] == preferred_model]
    pool = preferred or candidates
    if not pool:
        raise RuntimeError(f"no eligible candidate for preferred model {preferred_model}")
    return sorted(pool, key=rank, reverse=True)[0]


def png_number(path: Path) -> int:
    """Return the numeric part of p<N>.png for stable visual ordering."""
    return int(path.stem[1:])


def key_image(folder: Path, key_step_id: int | None) -> Path | None:
    """Prefer the image from the judged key step, then fall back to the latest image."""
    images = sorted(folder.glob("p*.png"), key=png_number)
    if not images:
        return None
    desired = folder / f"p{key_step_id}.png"
    return desired if desired.exists() else images[-1]


def common_pair_image(full_dir: Path, wrong_dir: Path, key_step_id: int | None) -> tuple[Path | None, Path | None]:
    """Use one matching trajectory image for each side of a WrongRender comparison."""
    full_images = {png_number(path): path for path in full_dir.glob("p*.png")}
    wrong_images = {png_number(path): path for path in wrong_dir.glob("p*.png")}
    common = sorted(set(full_images) & set(wrong_images))
    if not common:
        return None, None
    selected = key_step_id if key_step_id in common else common[-1]
    return full_images[selected], wrong_images[selected]


def asset_path(path: Path | None, out: Path) -> str:
    return "" if path is None else path.relative_to(out).as_posix()


def one_line(value: object) -> str:
    return " ".join(str(value).split())


TEXT_STEP = re.compile(
    r"\*\*Step\s+(\d+)\s+\(Text\):\*\*\s*(.*?)(?=\n\*\*Step\s+\d+\s+\((?:Text|Action Description)\):\*\*|\n\*\*Final Answer:\*\*|\Z)",
    re.DOTALL,
)
ACTION_STEP = re.compile(
    r"\*\*Step\s+(\d+)\s+\(Action Description\):\*\*\s*```json\s*(\{.*?\})\s*```",
    re.DOTALL,
)


def read_trajectory_parts(steps_path: Path, key_step_id: int | None) -> dict:
    """Extract the paper-facing thought/action/feedback fields from a saved trajectory."""
    text = steps_path.read_text(encoding="utf-8")
    thought_by_step = {int(step): one_line(content) for step, content in TEXT_STEP.findall(text)}
    action_by_step: dict[int, dict] = {}
    for step, payload in ACTION_STEP.findall(text):
        try:
            action_by_step[int(step)] = json.loads(payload)
        except json.JSONDecodeError:
            continue

    if key_step_id not in thought_by_step:
        key_step_id = max(thought_by_step, default=None)
    action_step_id = key_step_id
    if action_step_id not in action_by_step:
        eligible = [step for step in action_by_step if key_step_id is None or step <= key_step_id]
        action_step_id = max(eligible, default=max(action_by_step, default=None))
    action = action_by_step.get(action_step_id, {})
    operations = []
    for item in action.get("action", []):
        name = str(item.get("type", "visual operation")).replace("_", " ")
        content = one_line(item.get("content", ""))
        operations.append(f"{name}{f' — {content}' if content else ''}")
    visual_action = one_line(action.get("visual_rationale", ""))
    if operations:
        visual_action = f"{visual_action} Requested operation: {'; '.join(operations)}.".strip()

    reasoning_steps = [
        f"Step {step}: {thought}" for step, thought in sorted(thought_by_step.items())
        if action_step_id is not None and step > action_step_id
    ]
    return {
        "key_step_id": key_step_id,
        "action_step_id": action_step_id,
        "key_textual_thought": thought_by_step.get(key_step_id, ""),
        "requested_visual_action": visual_action,
        "subsequent_reasoning": " ".join(reasoning_steps),
    }


def crop_paper_image(source: Path, destination: Path) -> None:
    """Create a display-only crop, removing isolated white headers/margins."""
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        background = image.getpixel((0, 0))
        is_near_white = min(background) >= 240 and max(background) - min(background) <= 12
        result = image
        if is_near_white:
            flat_background = Image.new("RGB", image.size, background)
            difference = ImageChops.difference(image, flat_background).convert("L")
            mask = difference.point(lambda value: 255 if value > 16 else 0)
            active_rows = [y for y in range(height) if mask.crop((0, y, width, y + 1)).getbbox()]
            groups: list[list[int]] = []
            for row in active_rows:
                if not groups or row > groups[-1][-1] + 12:
                    groups.append([row])
                else:
                    groups[-1].append(row)
            if groups and width / height > 1.5:
                # The long central component is the actual figure; short isolated
                # components above/below are headers such as "Figure:".
                main_rows = max(groups, key=len)
                top, bottom = main_rows[0], main_rows[-1] + 1
                local_box = mask.crop((0, top, width, bottom)).getbbox()
                if local_box:
                    left, local_top, right, local_bottom = local_box
                    top += local_top
                    bottom = top + (local_bottom - local_top)
                    padding_x = max(8, round((right - left) * 0.025))
                    padding_y = max(8, round((bottom - top) * 0.025))
                    result = image.crop((max(0, left - padding_x), max(0, top - padding_y), min(width, right + padding_x), min(height, bottom + padding_y)))
            elif mask.getbbox():
                left, top, right, bottom = mask.getbbox()
                padding_x = max(8, round((right - left) * 0.025))
                padding_y = max(8, round((bottom - top) * 0.025))
                result = image.crop((max(0, left - padding_x), max(0, top - padding_y), min(width, right + padding_x), min(height, bottom + padding_y)))
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.save(destination, optimize=True)


def build_paper_images(manifest: list[dict], out: Path) -> dict[str, str]:
    """Prepare cropped image assets while keeping original trajectory files intact."""
    assets: dict[str, str] = {}
    sources: list[Path] = []
    for row in manifest:
        full_dir = out / row["folder"] / "full"
        sources.extend([full_dir / "p0.png", key_image(full_dir, row["key_step_id"])])
        if row["example_type"] == "E2_wrongrender":
            full_image, wrong_image = common_pair_image(full_dir, out / row["folder"] / "wrong_render", row["key_step_id"])
            sources.extend([full_image, wrong_image])
    for source in dict.fromkeys(path for path in sources if path is not None):
        destination = out / "paper_images" / source.relative_to(out)
        crop_paper_image(source, destination)
        assets[source.relative_to(out).as_posix()] = destination.relative_to(out).as_posix()
    return assets


def render_html(manifest: list[dict], out: Path) -> None:
    """Write a standalone, readable gallery alongside the paper-ready assets."""
    def field(label: str, value: object) -> str:
        return f"<p><b>{html.escape(label)}:</b> {html.escape(one_line(value))}</p>"

    parts = ["""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Appendix E — Qualitative Examples (1,200)</title>
<style>
body{margin:0;background:#f5f7fb;color:#182235;font:15px/1.55 Arial,sans-serif}main{max-width:1440px;margin:auto;padding:34px}
h1{margin:0 0 6px}h2{border-bottom:2px solid #253a5c;margin-top:42px;padding-bottom:7px}.lead{color:#516176;max-width:1000px}
.category{margin-top:28px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:18px}.card{background:#fff;border:1px solid #dce3ef;border-radius:12px;padding:18px;box-shadow:0 2px 7px #15233a0a}.tag{display:inline-block;background:#eaf1ff;color:#214b8b;border-radius:20px;padding:2px 10px;margin-right:5px;font-weight:600}.warn{background:#fff1e7;color:#9a4c16}.images{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.images.triple{grid-template-columns:repeat(3,minmax(0,1fr))}.panel{margin:0}.panel figcaption{font-size:13px;color:#5f6d82;margin:4px 0}.panel img{width:100%;height:230px;object-fit:contain;background:#eef1f5;border-radius:7px}.card p{margin:7px 0}.links a{color:#1f5eae;text-decoration:none}.note{background:#edf5ff;border-left:4px solid #3978c6;padding:12px 14px;border-radius:6px;max-width:1100px}@media(max-width:650px){main{padding:18px}.grid{grid-template-columns:1fr}.images,.images.triple{grid-template-columns:1fr}.panel img{height:auto}}
</style></head><body><main>
<h1>Appendix E. Qualitative Examples</h1>
<p class=\"lead\">Representative VAoT-Full trajectories and paired WrongRender interventions selected from the final 1,200-sample evaluation. The three paper categories use the fixed taxonomy: 2D Structured Reasoning, 3D Scene Reasoning, and Real-world Visual Reasoning.</p>
<div class=\"note\"><b>Reading guide.</b> E.1 contains one successful closed-loop trajectory and one diagnostic trajectory per category. E.2 shows a paired Full / WrongRender comparison: the requested visual action is preserved, while task-relevant visual evidence is altered.</div>"""]

    display_name = {"2D": "2D Structured Reasoning", "3D": "3D Scene Reasoning", "Real": "Real-world Visual Reasoning"}
    parts.append("<h2>E.1 Representative VAoT-Full trajectories</h2>")
    for category in CATEGORIES:
        parts.append(f"<section class=\"category\"><h3>{html.escape(display_name[category])}</h3><div class=\"grid\">")
        for kind in ("E1_success", "E1_diagnostic"):
            row = next(item for item in manifest if item["example_type"] == kind and item["paper_category"] == category)
            image = key_image(out / row["folder"] / "full", row["key_step_id"])
            title = "Successful trajectory" if kind == "E1_success" else "Diagnostic trajectory"
            extra = row["key_step_reason"] if kind == "E1_success" else (row["render_faithfulness_reason"] if row["render_faithfulness"] < 1 else row["feedback_uptake_reason"])
            parts.append("<article class=\"card\">")
            parts.append(f"<span class=\"tag {'warn' if kind == 'E1_diagnostic' else ''}\">{title}</span><span class=\"tag\">{html.escape(row['model'])}</span>")
            parts.append(field("Task", row["task_key"]))
            parts.append(field("Question", row["question"]))
            parts.append(field("Answer / ground truth", f"{row['full_answer']} / {row['ground_truth']}"))
            parts.append(field("Process scores (AR / RF / FU)", f"{row['action_relevance']} / {row['render_faithfulness']} / {row['feedback_uptake']}"))
            parts.append(field("Key textual thought (before the visual action)", row["key_textual_thought"]))
            parts.append(field("Requested visual action", row["requested_visual_action"]))
            parts.append(field("Subsequent reasoning (after seeing the render)", row["full_subsequent_reasoning"]))
            parts.append(field("Interpretation", extra))
            if image:
                parts.append(f"<div class=\"images\"><figure class=\"panel\"><figcaption>Key visual step (p{png_number(image)})</figcaption><img src=\"{asset_path(image, out)}\" loading=\"lazy\"></figure><figure class=\"panel\"><figcaption>Original image</figcaption><img src=\"{row['folder']}/full/p0.png\" loading=\"lazy\"></figure></div>")
            parts.append(f"<p class=\"links\"><a href=\"{row['folder']}/full/steps.md\">Trajectory (steps.md)</a> · <a href=\"{row['folder']}/case_metadata.json\">Metadata</a></p></article>")
        parts.append("</div></section>")

    parts.append("<h2>E.2 Representative WrongRender cases</h2><p class=\"lead\">All three comparisons have a semantically changed answer, are correct under VAoT-Full, and are incorrect under VAoT-WrongRender.</p>")
    for category in CATEGORIES:
        row = next(item for item in manifest if item["example_type"] == "E2_wrongrender" and item["paper_category"] == category)
        full_dir, wrong_dir = out / row["folder"] / "full", out / row["folder"] / "wrong_render"
        full_image, wrong_image = common_pair_image(full_dir, wrong_dir, row["key_step_id"])
        parts.append(f"<section class=\"category\"><h3>{html.escape(display_name[category])}</h3><article class=\"card\">")
        parts.append(f"<span class=\"tag\">{html.escape(row['model'])}</span><span class=\"tag warn\">Semantic answer change</span>")
        parts.append(field("Task", row["task_key"]))
        parts.append(field("Question", row["question"]))
        parts.append(field("VAoT-Full answer (correct)", row["full_answer"]))
        parts.append(field("VAoT-WrongRender answer (incorrect)", row["wrongrender_answer"]))
        parts.append(field("Shared requested visual action", row["requested_visual_action"]))
        parts.append(field("VAoT-Full subsequent reasoning", row["full_subsequent_reasoning"]))
        parts.append(field("VAoT-WrongRender subsequent reasoning", row["wrongrender_subsequent_reasoning"]))
        parts.append(field("Why this is a valid intervention", row["action_relevance_reason"]))
        if full_image and wrong_image:
            parts.append(f"<div class=\"images triple\"><figure class=\"panel\"><figcaption>Original</figcaption><img src=\"{row['folder']}/full/p0.png\" loading=\"lazy\"></figure><figure class=\"panel\"><figcaption>VAoT-Full, matched p{png_number(full_image)}</figcaption><img src=\"{asset_path(full_image, out)}\" loading=\"lazy\"></figure><figure class=\"panel\"><figcaption>VAoT-WrongRender, matched p{png_number(wrong_image)}</figcaption><img src=\"{asset_path(wrong_image, out)}\" loading=\"lazy\"></figure></div>")
        parts.append(f"<p class=\"links\"><a href=\"{row['folder']}/full/steps.md\">Full trajectory</a> · <a href=\"{row['folder']}/wrong_render/steps.md\">WrongRender trajectory</a> · <a href=\"{row['folder']}/case_metadata.json\">Metadata</a></p></article></section>")
    parts.append("</main></body></html>")
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")


PAPER_COPY = {
    ("E1_success", "2D"): ("Rank the power dissipation of three resistor networks.", r"R2 has three branches sharing the same two terminals, so it is a parallel network.", "Highlight the three R2 branches and their shared top/bottom terminals.", r"The highlighted structure gives \(R_{2,\mathrm{eq}}=0.5\Omega\); with \(R_1=1\Omega\) and \(R_3=2\Omega\), this yields \(P_2>P_1>P_3\)."),
    ("E1_diagnostic", "2D"): ("Count the points on a convex hull.", "Test whether the segment from the leftmost point to the topmost point is a hull edge.", "Draw the candidate hull edge and label the supposedly empty outer half-plane.", "The later reasoning treats the four extreme points as a complete hull and answers 4; the cluttered, ambiguous overlay does not reliably rule out the remaining boundary points."),
    ("E1_success", "3D"): ("Count objects satisfying two spatial-and-attribute conditions.", "The small green bus is the only small object left of the fighter; the second condition requires a big, shiny object behind the blue van.", "Mark the small green bus and make the left-of-fighter / behind-van relations explicit.", "The rendered cues support one qualifying green bus and one qualifying gold station wagon, giving the correct total of 2."),
    ("E1_diagnostic", "3D"): ("Identify the material of a relationally specified gray bus.", "Locate the gray bus to the left of the gray metal reference object before judging its material.", "Annotate the target gray bus on the left.", "The callout lands on a different object, but later reasoning still asserts rubber: a target-grounding failure (RF=0, FU=0)."),
    ("E1_success", "Real"): ("Infer what the woman is doing in a classroom scene.", "The woman is seated at a desk and actively using an open laptop, the decisive activity cue.", "Box the woman together with her laptop.", "The highlighted laptop use and classroom context support the conclusion that she is studying."),
    ("E1_diagnostic", "Real"): ("Predict the next robot action to pick up the 1-pin mahjong tile.", "First localize the 1-pin tile, then move the gripper to a pre-grasp pose above it.", "Place a callout on the 1-pin mahjong tile.", "The annotation is only partially aligned with the target, yet the subsequent grasp plan relies on it and produces an incorrect action vector."),
    ("E2_wrongrender", "2D"): ("Determine the refractive index of an isosceles prism with one mirrored side.", "Mark the apex and equal base angles of the prism.", r"The reflected path gives \(r+r'=75^\circ\); with \(r=r'\), this yields \(r=37.5^\circ\) and \(\mu\approx1.54\).", r"The corrupted path is read as \(r+r'=110^\circ\); with \(r=r'\), this yields \(r=55^\circ\) and \(\mu\approx1.15\)."),
    ("E2_wrongrender", "3D"): ("Count small objects left of the fighter or big, shiny objects behind the blue van.", "Make the left-of-fighter and behind-van reference relations visually explicit.", "The correct cues identify one green bus and one gold station wagon, so the total is 2.", "The corrupted highlights make the model count three small-left and two big-shiny-behind objects, changing the answer to 5."),
    ("E2_wrongrender", "Real"): ("Infer the intended role of a seated figure in a cafe setting.", "Highlight the branded tie as evidence of the figure's commercial role.", "The visible Carlsberg branding supports a promotional display / store-advertising interpretation.", "After the brand evidence is corrupted into a generic patterned tie, the model describes a generic decorative mannequin."),
}

PAPER_ANSWERS = {
    ("E1_success", "2D"): r"\(P_2>P_1>P_3\).",
    ("E1_diagnostic", "2D"): "4 (incorrect; ground truth: 7).",
    ("E1_success", "3D"): "2.",
    ("E1_diagnostic", "3D"): "Rubber (incorrect; ground truth: metal).",
    ("E1_success", "Real"): "Studying.",
    ("E1_diagnostic", "Real"): "Incorrect pre-grasp / grasp action vector.",
    ("E2_wrongrender", "2D"): (r"\(\mu\approx1.54\).", r"\(\mu\approx1.15\)."),
    ("E2_wrongrender", "3D"): ("2.", "5."),
    ("E2_wrongrender", "Real"): ("Promotional display / store advertising.", "Generic decorative mannequin."),
}


def render_html(manifest: list[dict], out: Path, paper_images: dict[str, str]) -> None:
    """Write compact panels intended for high-resolution paper screenshots."""
    def field(label: str, value: str) -> str:
        return f'<div class="row"><b>{html.escape(label)}</b><span class="md">{html.escape(value)}</span></div>'

    def paper_asset(source: Path) -> str:
        return paper_images[source.relative_to(out).as_posix()]

    def is_wide(source: Path) -> bool:
        with Image.open(out / paper_asset(source)) as image:
            return image.width / image.height > 1.7

    head = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Appendix E - Qualitative Examples</title><link rel="stylesheet" href="assets/katex/katex.min.css"><style>
body{margin:0;background:#f3f5f8;color:#121a28;font:28px/1.46 Arial,Helvetica,sans-serif}main{max-width:2160px;margin:auto;padding:48px}h1{font-size:46px;margin:0 0 10px}h2{font-size:38px;border-bottom:3px solid #1d3659;margin:58px 0 20px;padding-bottom:10px}h3{font-size:33px;margin:38px 0 14px}.lead{font-size:27px;color:#42536d;max-width:1750px}.note{font-size:26px;background:#e9f2ff;border-left:6px solid #286fc4;padding:16px 20px;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:26px}.card{background:#fff;border:1px solid #cbd6e6;border-radius:15px;padding:26px;box-shadow:0 2px 8px #1d35531a}.tag{display:inline-block;font-size:25px;line-height:1.2;background:#e8f1ff;color:#164a91;border-radius:22px;padding:5px 13px;margin:0 8px 12px 0;font-weight:700}.warn{background:#fff0e7;color:#9a4c16}.task{font-size:29px;font-weight:700;margin:4px 0 15px}.score{font-size:27px;font-weight:700;color:#234678;margin:4px 0 18px}.images{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:17px 0 22px;align-items:start}.images.wide{grid-template-columns:1fr}.images.triple{grid-template-columns:repeat(3,minmax(0,1fr))}.panel{margin:0}.panel figcaption{font-size:25px;font-weight:700;margin:0 0 7px;color:#41516a}.panel img{display:block;width:100%;height:auto;object-fit:contain;background:#edf0f4;border-radius:9px}.row{font-size:27px;margin:15px 0}.row b{display:block;color:#203a60;margin-bottom:3px}.md{display:block}.links{font-size:22px;margin:20px 0 0}.links a{color:#1b5fab;text-decoration:none}.e2{margin-top:26px}.katex-display{margin:.45em 0}@media(max-width:1000px){body{font-size:22px}main{padding:22px}.grid,.images,.images.triple{grid-template-columns:1fr}.row{font-size:22px}}@media print{body{background:#fff}main{max-width:none;padding:0}.card{box-shadow:none;break-inside:avoid}.links{display:none}}</style></head><body><main><h1>Appendix E. Qualitative Examples</h1><p class="lead">Compact paper-ready panels selected from the final 1,200-sample evaluation. Complete trajectories remain linked below each case, while the panels show only the evidence needed to interpret the result.</p><div class="note"><b>Reading guide.</b> AR = Action Relevance; RF = Render Faithfulness; FU = Feedback Uptake. Mathematics and Markdown are rendered locally with KaTeX, so the page works offline.</div>"""
    parts = [head]
    names = {"2D": "2D Structured Reasoning", "3D": "3D Scene Reasoning", "Real": "Real-world Visual Reasoning"}
    parts.append("<h2>E.1 Representative VAoT-Full trajectories</h2>")
    for category in CATEGORIES:
        parts.append(f'<section><h3>{names[category]}</h3><div class="grid">')
        for kind in ("E1_success", "E1_diagnostic"):
            row = next(item for item in manifest if item["example_type"] == kind and item["paper_category"] == category)
            task, thought, action, use = PAPER_COPY[(kind, category)]
            image = key_image(out / row["folder"] / "full", row["key_step_id"])
            title, suffix = ("Successful case", "Feedback use") if kind == "E1_success" else ("Diagnostic case", "Diagnosis")
            parts.append(f'<article class="card"><span class="tag {"warn" if kind == "E1_diagnostic" else ""}">{title}</span><span class="tag">{html.escape(row["model"])}</span><div class="task">{html.escape(task)}</div><div class="score">AR / RF / FU: {row["action_relevance"]:.1f} / {row["render_faithfulness"]:.1f} / {row["feedback_uptake"]:.1f}</div>')
            if image:
                original = out / row["folder"] / "full" / "p0.png"
                layout = "images wide" if is_wide(image) else "images"
                parts.append(f'<div class="{layout}"><figure class="panel"><figcaption>Original</figcaption><img src="{paper_asset(original)}"></figure><figure class="panel"><figcaption>Rendered visual state</figcaption><img src="{paper_asset(image)}"></figure></div>')
            parts += [field("Key thought", thought), field("Visual action", action), field(suffix, use), field("Final answer", PAPER_ANSWERS[(kind, category)])]
            parts.append(f'<p class="links"><a href="{row["folder"]}/full/steps.md">Open complete trajectory</a> | <a href="{row["folder"]}/case_metadata.json">Metadata</a></p></article>')
        parts.append("</div></section>")
    parts.append("<h2>E.2 Representative WrongRender cases</h2>")
    for category in CATEGORIES:
        row = next(item for item in manifest if item["example_type"] == "E2_wrongrender" and item["paper_category"] == category)
        task, action, full_reasoning, wrong_reasoning = PAPER_COPY[("E2_wrongrender", category)]
        full_image, wrong_image = common_pair_image(out / row["folder"] / "full", out / row["folder"] / "wrong_render", row["key_step_id"])
        parts.append(f'<section class="e2"><h3>{names[category]}</h3><article class="card"><span class="tag">{html.escape(row["model"])}</span><span class="tag warn">Semantic answer change</span><div class="task">{html.escape(task)}</div>')
        if full_image and wrong_image:
            original = out / row["folder"] / "full" / "p0.png"
            parts.append(f'<div class="images triple"><figure class="panel"><figcaption>Original</figcaption><img src="{paper_asset(original)}"></figure><figure class="panel"><figcaption>VAoT-Full render</figcaption><img src="{paper_asset(full_image)}"></figure><figure class="panel"><figcaption>VAoT-WrongRender</figcaption><img src="{paper_asset(wrong_image)}"></figure></div>')
        full_answer, wrong_answer = PAPER_ANSWERS[("E2_wrongrender", category)]
        parts += [field("Shared visual action", action), field("VAoT-Full reasoning", full_reasoning), field("VAoT-WrongRender reasoning", wrong_reasoning), field("Full answer (correct)", full_answer), field("WrongRender answer (incorrect)", wrong_answer)]
        parts.append(f'<p class="links"><a href="{row["folder"]}/full/steps.md">Full trajectory</a> | <a href="{row["folder"]}/wrong_render/steps.md">WrongRender trajectory</a></p></article></section>')
    parts.append("</main><script src=\"assets/katex/katex.min.js\"></script><script src=\"assets/katex/auto-render.min.js\"></script><script>function md(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\\*\\*(.+?)\\*\\*/g,'<strong>$1</strong>').replace(/\\n/g,'<br>')}var bs=String.fromCharCode(92);document.querySelectorAll('.md').forEach(function(n){n.innerHTML=md(n.textContent);renderMathInElement(n,{delimiters:[{left:bs+'[',right:bs+']',display:true},{left:bs+'(',right:bs+')',display:false}],throwOnError:false});});</script></body></html>")
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")


STRICT_E1 = {
    ("E1_success", "2D"): ("Which resistor configuration dissipates the most power, which the least, and what is their order?", r"R2 has three branches sharing the same top and bottom terminals, so they form a parallel network.", "Highlight the three R2 branches and their shared top and bottom terminals.", r"The three branches have resistances \(2\Omega\), \(1\Omega\), and \(2\Omega\), giving \(R_{2,\mathrm{eq}}=0.5\Omega\) and therefore \(P_2>P_1>P_3\).", r"\(P_{R2}>P_{R1}>P_{R3}\); configuration R2 dissipates the most power, and R3 the least."),
    ("E1_diagnostic", "2D"): ("How many of the given plane points lie on their convex hull?", "Test whether the segment from the leftmost point to the topmost point is a hull edge.", "Draw the candidate hull edge and label the empty outer side.", "The four coordinate-extreme points are connected as hull edges, and all remaining points are treated as interior.", "4 (ground truth: 7)."),
    ("E1_success", "3D"): ("How many objects are small things left of the rubber fighter or big shiny things behind the large blue rubber thing?", "The small green bus is the only small object left of the fighter.", "Mark the small green bus on the left of the fighter.", "The green bus is the one small-left object, and the gold station wagon is the one big shiny object behind the van, giving a total of 2.", "2."),
    ("E1_diagnostic", "3D"): ("What material is the gray bus left of the gray metal object right of the big purple truck made of?", "First locate the gray metal object to the right of the big purple truck, then identify the gray bus to its left.", "Annotate the gray bus on the left.", "The bus appears matte and non-reflective, so its material is identified as rubber.", "Rubber (ground truth: metal)."),
    ("E1_success", "Real"): ("What is the woman doing based on her surroundings and activity?", "The woman is seated at a desk and interacting with an open laptop.", "Annotate the woman using the laptop.", "The laptop use in a classroom setting leads to the conclusion that she is studying or working.", "Studying (ground truth: Studying)."),
    ("E1_diagnostic", "Real"): ("Predict the next immediate 7-dimensional action vector to pick up the 1-pin mahjong tile.", "Identify the 1-pin tile before moving the gripper toward a pre-grasp pose.", "Annotate the 1-pin mahjong tile.", "Move the gripper down toward the identified tile, close the gripper, and then lift upward.", "Prediction: [0.0100, 0.2550, 0.2600, -3.1411, 0.0064, -2.2992, 1.0000]. Ground truth: [0.0320, 0.2976, 0.3053, 3.1365, 0.0124, -2.3528, 1.0000]."),
}

STRICT_E2 = {
    "2D": ("Mark the apex and equal base angles of the isosceles prism.", r"The reflected internal path gives \(r+r'=75^\circ\). With \(r=r'\), this yields \(r=37.5^\circ\) and \(\mu\approx1.54\).", r"The corrupted path is read as \(r+r'=110^\circ\). With \(r=r'\), this yields \(r=55^\circ\) and \(\mu\approx1.15\)."),
    "3D": ("Make the left-of-fighter and behind-van relations visually explicit.", "One small green bus is left of the fighter and one gold station wagon is behind the van, giving 2.", "The tagged objects give three small-left objects and two big-shiny-behind objects, giving 5."),
    "Real": ("Highlight the branded tie on the seated figure.", "The visible Carlsberg branding is used to identify the figure as a commercial promotional display for the establishment.", "The figure is described as a life-sized decorative mannequin and novelty photo prop for cafe visitors."),
}


def render_html_strict(manifest: list[dict], out: Path, paper_images: dict[str, str]) -> None:
    """Write the strict Appendix E layout: only the fields permitted by the specification."""
    def paper_asset(source: Path) -> str:
        return paper_images[source.relative_to(out).as_posix()]

    def field(label: str, value: str) -> str:
        return f'<div class="field"><div class="label">{html.escape(label)}</div><div class="md">{html.escape(value)}</div></div>'

    header = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E Qualitative Examples</title><link rel="stylesheet" href="assets/katex/katex.min.css"><style>
body{margin:0;background:#f5f6f8;color:#111827;font:23px/1.42 Arial,Helvetica,sans-serif}main{max-width:2200px;margin:auto;padding:42px}h1{font-size:46px;margin:0 0 34px}h2{font-size:40px;margin:48px 0 10px;padding-bottom:10px;border-bottom:3px solid #223b61}h3{font-size:31px;margin:32px 0 15px}h4{font-size:29px;margin:0 0 16px}.score{font-size:25px;font-weight:700;color:#1f477f;margin:14px 0 22px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:25px}.card{background:#fff;border:1px solid #cfd8e6;border-radius:14px;padding:24px;box-shadow:0 2px 7px #19314c12}.case-type{font-size:27px;font-weight:700;color:#244c84;margin-bottom:13px}.images{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:13px 0 22px;align-items:start}.images.triple{grid-template-columns:repeat(3,minmax(0,1fr))}.panel{margin:0}.panel figcaption{font-size:25px;font-weight:700;color:#3b4d68;margin-bottom:6px}.panel img{display:block;width:100%;height:auto;object-fit:contain;background:#f1f3f6;border-radius:8px}.field{margin:15px 0}.label{font-size:27px;font-weight:700;color:#1f3e69;margin-bottom:3px}.md{font-size:24px}.reasoning-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin-top:20px}.katex-display{margin:.4em 0}@media(max-width:1050px){main{padding:22px}.grid,.images,.images.triple,.reasoning-grid{grid-template-columns:1fr}body{font-size:20px}.md{font-size:21px}}@media print{body{background:#fff}main{max-width:none;padding:0}.card{box-shadow:none;break-inside:avoid}}</style></head><body><main><h1>E Qualitative Examples</h1>"""
    names = {"2D": "2D Structured Reasoning", "3D": "3D Scene Reasoning", "Real": "Real-world Visual Reasoning"}
    parts = [header, "<h2>E.1 Representative VAoT-Full Trajectories</h2>", "<p>AR = Action Relevance; RF = Render Faithfulness; FU = Feedback Uptake.</p>"]
    for category in CATEGORIES:
        parts.append(f'<section><h3>{names[category]}</h3><div class="grid">')
        for kind in ("E1_success", "E1_diagnostic"):
            row = next(item for item in manifest if item["example_type"] == kind and item["paper_category"] == category)
            question, thought, action, reasoning, answer = STRICT_E1[(kind, category)]
            render = key_image(out / row["folder"] / "full", row["key_step_id"])
            original = out / row["folder"] / "full" / "p0.png"
            title = "Successful trajectory" if kind == "E1_success" else "Diagnostic trajectory"
            parts.append(f'<article class="card"><h4>{title}</h4>')
            parts += [field("Question", question), f'<div class="score">AR / RF / FU: {row["action_relevance"]:.1f} / {row["render_faithfulness"]:.1f} / {row["feedback_uptake"]:.1f}</div>']
            parts.append(f'<div class="images"><figure class="panel"><figcaption>Original image</figcaption><img src="{paper_asset(original)}"></figure><figure class="panel"><figcaption>Rendered visual state</figcaption><img src="{paper_asset(render)}"></figure></div>')
            parts += [field("Key textual thought", thought), field("Visual action", action), field("Subsequent reasoning", reasoning), field("Final answer", answer), "</article>"]
        parts.append("</div></section>")
    parts.append("<h2>E.2 Representative WrongRender Cases</h2>")
    for category in CATEGORIES:
        row = next(item for item in manifest if item["example_type"] == "E2_wrongrender" and item["paper_category"] == category)
        action, full_reasoning, wrong_reasoning = STRICT_E2[category]
        full_dir, wrong_dir = out / row["folder"] / "full", out / row["folder"] / "wrong_render"
        correct, wrong = common_pair_image(full_dir, wrong_dir, row["key_step_id"])
        original = full_dir / "p0.png"
        parts.append(f'<section><h3>{names[category]}</h3><article class="card">')
        parts.append(field("Requested visual action", action))
        parts.append(f'<div class="images triple"><figure class="panel"><figcaption>Original image</figcaption><img src="{paper_asset(original)}"></figure><figure class="panel"><figcaption>Correct render</figcaption><img src="{paper_asset(correct)}"></figure><figure class="panel"><figcaption>WrongRender</figcaption><img src="{paper_asset(wrong)}"></figure></div>')
        parts.append('<div class="reasoning-grid">' + field("VAoT-Full subsequent reasoning / answer", full_reasoning) + field("VAoT-WrongRender subsequent reasoning / answer", wrong_reasoning) + "</div></article></section>")
    parts.append("</main><script src=\"assets/katex/katex.min.js\"></script><script src=\"assets/katex/auto-render.min.js\"></script><script>var bs=String.fromCharCode(92);document.querySelectorAll('.md').forEach(function(n){renderMathInElement(n,{delimiters:[{left:bs+'[',right:bs+']',display:true},{left:bs+'(',right:bs+')',display:false}],throwOnError:false});});</script></body></html>")
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    records: list[dict] = []
    for model, tag, semantic_run in MODELS:
        full = map_rows(load(EVAL / f"answer_{tag}_full_1200.jsonl"))
        wrong = map_rows(load(EVAL / f"answer_{tag}_wrong_render_1200.jsonl"))
        process = load(EVAL / f"process_eval_{tag}_full_1200.jsonl")
        changes = map_rows(load(SEMANTIC / semantic_run / "answer_change_judge.jsonl"))
        for process_row in process:
            if process_row.get("status") != "ok":
                continue
            key = str(process_row["task_key"])
            full_row, wrong_row, change = full[key], wrong[key], changes[key]
            full_dir = ROOT / str(process_row["output_dir"])
            wrong_dir = candidate_wrong_dir(model, str(process_row["relative_source_dir"]), int(process_row["sample_id"]), str(process_row["evaluation_split"]))
            records.append({
                "model": model, "task_key": key, "paper_category": process_row["paper_category"],
                "source": process_row["relative_source_dir"], "sample_id": int(process_row["sample_id"]),
                "question": process_row.get("question", ""), "ground_truth": process_row.get("ground_truth", ""),
                "full_answer": full_row.get("final_answer", ""), "wrongrender_answer": wrong_row.get("final_answer", ""),
                "full_correct": bool(full_row["correct"]), "wrongrender_correct": bool(wrong_row["correct"]),
                "answer_changed_semantic": bool(change["answer_changed"]),
                "action_relevance": float(process_row["action_relevance"]),
                "render_faithfulness": float(process_row["render_faithfulness"]),
                "feedback_uptake": float(process_row["feedback_uptake"]),
                "key_step_id": process_row.get("key_step_id"),
                "key_step_reason": process_row.get("key_step_reason", ""),
                "action_relevance_reason": process_row.get("action_relevance_reason", ""),
                "render_faithfulness_reason": process_row.get("render_faithfulness_reason", ""),
                "feedback_uptake_reason": process_row.get("feedback_uptake_reason", ""),
                "full_dir": full_dir, "wrong_dir": wrong_dir,
            })

    selections: list[dict] = []
    for category in CATEGORIES:
        success = [r for r in records if r["paper_category"] == category and r["full_correct"] and r["action_relevance"] == r["render_faithfulness"] == r["feedback_uptake"] == 1 and r["full_dir"].is_dir()]
        chosen = choose(success, PREFERRED[("E1_success", category)], lambda r: (len(list(r["full_dir"].glob("p*.png"))), r["source"], -r["sample_id"]))
        chosen["example_type"] = "E1_success"
        selections.append(dict(chosen))

        diagnostic = [r for r in records if r["paper_category"] == category and r["action_relevance"] == 1 and (r["render_faithfulness"] < 1 or r["feedback_uptake"] < 1) and not r["full_correct"] and r["full_dir"].is_dir()]
        chosen = choose(diagnostic, PREFERRED[("E1_diagnostic", category)], lambda r: (1 if r["render_faithfulness"] < 1 else 0, 1 if r["feedback_uptake"] < 1 else 0, len(list(r["full_dir"].glob("p*.png"))), -r["sample_id"]))
        chosen["example_type"] = "E1_diagnostic"
        selections.append(dict(chosen))

        wrong_cases = [r for r in records if r["paper_category"] == category and r["full_correct"] and not r["wrongrender_correct"] and r["answer_changed_semantic"] and r["feedback_uptake"] >= 0.5 and r["full_dir"].is_dir() and r["wrong_dir"].is_dir()]
        fixed = FIXED_E2_SELECTIONS.get(category)
        if fixed:
            chosen = next(
                r for r in wrong_cases
                if (r["model"], r["task_key"]) == fixed
            )
        else:
            chosen = choose(wrong_cases, PREFERRED[("E2_wrongrender", category)], lambda r: (r["feedback_uptake"], r["render_faithfulness"], len(list(r["full_dir"].glob("p*.png"))), -r["sample_id"]))
        chosen["example_type"] = "E2_wrongrender"
        selections.append(dict(chosen))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if not KATEX_ASSETS.is_dir():
        raise RuntimeError(f"Missing local KaTeX assets: {KATEX_ASSETS}")
    copy_tree(KATEX_ASSETS, OUT / "assets" / "katex")
    manifest: list[dict] = []
    for index, record in enumerate(selections, 1):
        folder = OUT / f"{index:02d}_{record['example_type']}_{record['paper_category']}_{record['model']}_{safe_name(record['task_key'])}"
        copy_tree(record["full_dir"], folder / "full")
        if record["example_type"] == "E2_wrongrender":
            copy_tree(record["wrong_dir"], folder / "wrong_render")
        entry = {key: value for key, value in record.items() if key not in {"full_dir", "wrong_dir"}}
        entry["folder"] = folder.name
        full_parts = read_trajectory_parts(folder / "full" / "steps.md", record["key_step_id"])
        entry["key_textual_thought"] = full_parts["key_textual_thought"]
        entry["requested_visual_action"] = full_parts["requested_visual_action"]
        entry["full_subsequent_reasoning"] = full_parts["subsequent_reasoning"]
        entry["full_visual_action_step"] = full_parts["action_step_id"]
        if record["example_type"] == "E2_wrongrender":
            wrong_parts = read_trajectory_parts(folder / "wrong_render" / "steps.md", record["key_step_id"])
            entry["wrongrender_visual_action_step"] = wrong_parts["action_step_id"]
            entry["wrongrender_subsequent_reasoning"] = wrong_parts["subsequent_reasoning"]
        (folder / "case_metadata.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append(entry)

    with (OUT / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(dict.fromkeys(key for row in manifest for key in row))
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Appendix E. Qualitative Examples", "", "## E.1 Representative VAoT-Full Trajectories", "", "Two cases are provided for each paper category: a successful closed-loop trajectory and a diagnostic trajectory with a process-level weakness.", ""]
    for category in CATEGORIES:
        for kind in ("E1_success", "E1_diagnostic"):
            row = next(r for r in manifest if r["example_type"] == kind and r["paper_category"] == category)
            label = "Successful trajectory" if kind == "E1_success" else "Diagnostic trajectory"
            lines += [f"### {category}: {label}", f"- Model/task: `{row['model']}` · `{row['task_key']}`", f"- Full answer: `{row['full_answer']}` (ground truth: `{row['ground_truth']}`; correct: {row['full_correct']})", f"- Process scores: Action Relevance={row['action_relevance']}, Render Faithfulness={row['render_faithfulness']}, Feedback Uptake={row['feedback_uptake']}", f"- Evidence: {row['render_faithfulness_reason'] if kind == 'E1_diagnostic' and row['render_faithfulness'] < 1 else row['feedback_uptake_reason'] if kind == 'E1_diagnostic' else row['key_step_reason']}", f"- Assets: `{row['folder']}/full/`", ""]
            lines += [f"- Key textual thought: {row['key_textual_thought']}", f"- Requested visual action: {row['requested_visual_action']}", f"- Subsequent reasoning: {row['full_subsequent_reasoning']}", ""]
    lines += ["## E.2 Representative WrongRender Cases", "", "Each pair preserves the requested action type but changes task-relevant visual evidence. The selected examples are semantic answer changes where VAoT-Full is correct and VAoT-WrongRender is incorrect.", ""]
    for category in CATEGORIES:
        row = next(r for r in manifest if r["example_type"] == "E2_wrongrender" and r["paper_category"] == category)
        lines += [f"### {category}: WrongRender intervention", f"- Model/task: `{row['model']}` · `{row['task_key']}`", f"- VAoT-Full: `{row['full_answer']}` (correct)", f"- VAoT-WrongRender: `{row['wrongrender_answer']}` (incorrect)", f"- Process scores from Full: Action Relevance={row['action_relevance']}, Render Faithfulness={row['render_faithfulness']}, Feedback Uptake={row['feedback_uptake']}", f"- Assets: `{row['folder']}/full/` and `{row['folder']}/wrong_render/`", ""]
        lines += [f"- Shared requested visual action: {row['requested_visual_action']}", f"- VAoT-Full subsequent reasoning: {row['full_subsequent_reasoning']}", f"- VAoT-WrongRender subsequent reasoning: {row['wrongrender_subsequent_reasoning']}", ""]
    (OUT / "appendix_E_qualitative_examples.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    paper_images = build_paper_images(manifest, OUT)
    render_html_strict(manifest, OUT, paper_images)
    print("\n".join(f"{r['example_type']} {r['paper_category']} {r['model']} {r['task_key']}" for r in manifest))


if __name__ == "__main__":
    main()
