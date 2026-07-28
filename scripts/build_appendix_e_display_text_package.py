"""Export the nine Appendix E cases as clean reviewer-facing display folders."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from build_appendix_e_qualitative_examples import (
    STRICT_E1,
    STRICT_E2,
    common_pair_image,
    key_image,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs" / "appendix_e_qualitative_examples_1200"
OUT = ROOT / "deliverables" / "See2Think_Appendix_E_Display_Text_Package_v2"

NAMES = {
    "2D": "2D Structured Reasoning",
    "3D": "3D Scene Reasoning",
    "Real": "Real-world Visual Reasoning",
}


def copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    shutil.copy2(source, destination)


def score(value: object) -> str:
    return f"{float(value):.1f}"


def e1_text(row: dict, original: str, rendered: str) -> str:
    question, thought, action, reasoning, answer = STRICT_E1[(row["example_type"], row["paper_category"])]
    kind = "Successful trajectory" if row["example_type"] == "E1_success" else "Diagnostic trajectory"
    state = " ".join(str(row["render_faithfulness_reason"]).split())
    return f"""# {NAMES[row['paper_category']]} — {kind}

## Question

{question}

## Original image

![Original image]({original})

## Key textual thought

{thought}

## Visual action

{action}

## Rendered visual state

![Rendered visual state]({rendered})

{state}

## Subsequent reasoning

{reasoning}

## Final answer

{answer}

## Process scores

- Action Relevance: {score(row['action_relevance'])}
- Render Faithfulness: {score(row['render_faithfulness'])}
- Feedback Uptake: {score(row['feedback_uptake'])}
"""


def e2_text(row: dict) -> str:
    action, full_reasoning, wrong_reasoning = STRICT_E2[row["paper_category"]]
    return f"""# {NAMES[row['paper_category']]} — WrongRender case

## Original image

![Original image](original.png)

## Requested visual action

{action}

## Correct render

![Correct render](correct_render.png)

## WrongRender

![WrongRender](wrong_render.png)

## VAoT-Full subsequent reasoning / answer

{full_reasoning}

## VAoT-WrongRender subsequent reasoning / answer

{wrong_reasoning}
"""


def main() -> None:
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    readme = [
        "# Appendix E display package",
        "",
        "Nine selected qualitative cases. Each folder contains only the images intended for display and `展示文字.md`.",
        "",
        "- E.1 folders: original image, rendered visual state, and the trajectory fields plus AR/RF/FU.",
        "- E.2 folders: original image, correct render, WrongRender, and the requested paired-comparison text.",
        "",
    ]
    for index, row in enumerate(manifest, 1):
        folder = SOURCE / row["folder"]
        target = OUT / f"{index:02d}_{row['example_type']}_{row['paper_category']}_{row['model']}_{row['task_key'].replace('/', '__').replace('::', '_')}"
        target.mkdir()
        full = folder / "full"
        original = full / "p0.png"
        copy(original, target / "original.png")

        if row["example_type"] == "E2_wrongrender":
            wrong = folder / "wrong_render"
            correct_image, wrong_image = common_pair_image(full, wrong, row["key_step_id"])
            if correct_image is None or wrong_image is None:
                raise RuntimeError(f"No paired render for {row['folder']}")
            copy(correct_image, target / "correct_render.png")
            copy(wrong_image, target / "wrong_render.png")
            text = e2_text(row)
        else:
            render = key_image(full, row["key_step_id"])
            if render is None:
                raise RuntimeError(f"No rendered state for {row['folder']}")
            copy(render, target / "rendered_visual_state.png")
            text = e1_text(row, "original.png", "rendered_visual_state.png")

        (target / "展示文字.md").write_text(text, encoding="utf-8")
        readme.append(f"- `{target.name}`")

    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
