import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def count_valid(tasks_path, output_root, subdir, require_render=True):
    tasks = json.load(open(ROOT / tasks_path, encoding="utf-8"))
    out = ROOT / output_root
    ok = 0
    first_missing = None
    by_source = Counter()
    for pos, task in enumerate(tasks):
        path = Path(task["path"])
        idx = int(task.get("id", task.get("index")))
        if not path.is_absolute():
            path = ROOT / path
        rel = path.parent.relative_to(ROOT / "annotation/dataset/data")
        d = out / rel / subdir / str(idx)
        steps = d / "steps.md"
        valid = steps.exists() and steps.stat().st_size > 0
        has_render = any(
            p.name.startswith("p")
            and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
            and p.name != "p0.png"
            and p.stat().st_size > 0
            for p in d.glob("p*")
        ) if d.exists() else False
        if require_render:
            valid = valid and has_render
        if valid:
            ok += 1
            by_source[str(rel).replace("\\", "/")] += 1
        elif first_missing is None:
            first_missing = {
                "pos": pos,
                "source": str(rel).replace("\\", "/"),
                "id": idx,
                "steps": steps.exists(),
                "render": has_render,
            }
    return len(tasks), ok, first_missing, dict(sorted(by_source.items()))


items = [
    ("full", "gemini", "json/tasks_see2thinkbench_1154task_available.json", "newtasks/final1154_gemini-3.5-flash_vaot_full_floor", "banana_gemini-3.5-flash_vaot_full", True),
    ("full", "gpt-5.5", "json/tasks_see2thinkbench_1154task_available.json", "newtasks/final1154_gpt-5.5_vaot_full_floor", "banana_gpt-5.5_vaot_full", True),
    ("full", "o3", "json/tasks_see2thinkbench_1154task_available.json", "newtasks/final1154_o3_vaot_full_floor", "banana_o3_vaot_full", True),
    ("no_render", "gpt-5.5", "json/run_tasks_need_600/gpt-5.5__vaot_no_render__need_600.json", "newtasks/final600_gpt-5.5_vaot_no_render", "banana_gpt-5.5_vaot_no_render", False),
    ("no_render", "o3", "json/run_tasks_need_600/o3__vaot_no_render__need_600.json", "newtasks/final600_o3_vaot_no_render", "banana_o3_vaot_no_render", False),
    ("no_render", "gemini", "json/run_tasks_need_600/gemini-3.5-flash__vaot_no_render__need_600.json", "newtasks/final600_gemini-3.5-flash_vaot_no_render", "banana_gemini-3.5-flash_vaot_no_render", False),
    ("wrong_render_need", "gpt-5.5", "json/run_tasks_need_600/gpt-5.5__valid_wrong_render_step1__need_590.json", "newtasks/final600_gpt-5.5_vaot_wrong_render_floor", "banana_gpt-5.5_vaot_wrong_render", True),
    ("wrong_render_need", "o3", "json/run_tasks_need_600/o3__valid_wrong_render_step1__need_534.json", "newtasks/final600_o3_vaot_wrong_render_floor", "banana_o3_vaot_wrong_render", True),
    ("wrong_render_need", "gemini", "json/run_tasks_need_600/gemini-3.5-flash__valid_wrong_render_step1__need_590.json", "newtasks/final600_gemini-3.5-flash_vaot_wrong_render_floor", "banana_gemini-3.5-flash_vaot_wrong_render", True),
]

for setting, model, tasks, out, subdir, render in items:
    total, ok, first_missing, by_source = count_valid(tasks, out, subdir, render)
    print(f"{setting:18s} {model:10s} valid={ok}/{total} missing={total-ok} first_missing={first_missing}")
    print(f"  by_source={by_source}")
