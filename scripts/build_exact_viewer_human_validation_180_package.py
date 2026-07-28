"""Build a portable package using the project's original trajectory-viewer UI."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CHECK = ROOT / "yzrcheck"
SOURCE_VIEWER = ROOT / "viewer"
OUTPUT = ROOT / "deliverables" / "See2Think_HumanAudit180_OriginalViewer_20260719"

MODELS = (("gpt-5.5", "gpt55"), ("o3", "o3"), ("gemini-3.5-flash", "gemini35flash"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_csv_line(line: str) -> list[str]:
    cells, current, quoted = [], "", False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            cells.append(current)
            current = ""
        else:
            current += char
    cells.append(current)
    return cells


def check_rows() -> list[dict[str, str]]:
    lines = (SOURCE_CHECK / "index.csv").read_text(encoding="utf-8-sig").splitlines()
    headers = parse_csv_line(lines[0])
    return [dict(zip(headers, parse_csv_line(line))) for line in lines[1:] if line.strip()]


def score(value: float) -> dict[str, float | int]:
    return {"score": int(round(value * 2)), "normalized_score": value}


def replacement_app() -> str:
    app = (SOURCE_VIEWER / "app.js").read_text(encoding="utf-8")
    app = re.sub(r'const TASKS_URL = ".*?";', 'const TASKS_URL = "../data/tasks_180.json";', app, count=1)
    app = re.sub(r'const FULL_AUDIT_URL = ".*?";', 'const FULL_AUDIT_URL = "../data/empty.jsonl";', app, count=1)
    app = re.sub(r'const YZR_CHECK_INDEX_URL = ".*?";', 'const YZR_CHECK_INDEX_URL = "../yzrcheck/index.csv";', app, count=1)
    app = re.sub(r'const YZR_MISSING_INDEX_URL = ".*?";', 'const YZR_MISSING_INDEX_URL = "../data/empty.csv";', app, count=1)
    app = re.sub(
        r'const SETTINGS = \[.*?\n\];',
        'const SETTINGS = [\n  { id: "full", label: "VAoT-Full", promptUrl: "../data/see2think_vaot_full.txt" },\n];',
        app,
        count=1,
        flags=re.S,
    )
    app = re.sub(
        r'const MODELS = \[.*?\n\];',
        'const MODELS = [\n  { id: "gpt-5.5", label: "GPT-5.5" },\n  { id: "o3", label: "o3" },\n  { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },\n];',
        app,
        count=1,
        flags=re.S,
    )
    app = re.sub(
        r'const PROCESS_JUDGES = \{.*?\n\};',
        'const PROCESS_JUDGES = {\n  "full::gpt-5.5": "../data/process_gpt55.jsonl",\n  "full::o3": "../data/process_o3.jsonl",\n  "full::gemini-3.5-flash": "../data/process_gemini35flash.jsonl",\n};',
        app,
        count=1,
        flags=re.S,
    )
    app = re.sub(
        r'const KEY_STEP_JUDGES = \{.*?\n\};',
        'const KEY_STEP_JUDGES = {\n  "full::gpt-5.5": "../data/key_gpt55.jsonl",\n  "full::o3": "../data/key_o3.jsonl",\n  "full::gemini-3.5-flash": "../data/key_gemini35flash.jsonl",\n};',
        app,
        count=1,
        flags=re.S,
    )
    app = re.sub(
        r'const ANSWER_JUDGES = \{.*?\n\};',
        'const ANSWER_JUDGES = {\n  "full::gpt-5.5": "../data/answer_gpt55.jsonl",\n  "full::o3": "../data/answer_o3.jsonl",\n  "full::gemini-3.5-flash": "../data/answer_gemini35flash.jsonl",\n};',
        app,
        count=1,
        flags=re.S,
    )
    app = re.sub(
        r'const SUMMARY_ANSWER_COLUMNS = \[.*?\n\];',
        'const SUMMARY_ANSWER_COLUMNS = [{ id: "full", label: "VAoT-Full" }];',
        app,
        count=1,
        flags=re.S,
    )
    app = app.replace(
        'function outputDir(setting, model, task) {\n  return `../final_results/${setting.id}/${model.id}/${relSourceDir(task.path)}/${Number(task.id)}`;\n}',
        'function outputDir(setting, model, task) {\n  const row = state.yzrByTaskModel.get(modelTaskKey(model.id, task.key));\n  return row ? `../yzrcheck/${row.case_dir}` : "";\n}',
    )
    app = app.replace(
        'async function loadSample(task) {\n  if (!state.dataCache.has(task.path)) state.dataCache.set(task.path, fetchJson(`../${task.path}`));\n  const rows = await state.dataCache.get(task.path);\n  return rows[Number(task.id)];\n}',
        'async function loadSample(task) {\n  return { question: task.question || "", answer: task.answer || "" };\n}',
    )
    app = app.replace(
        'function sampleImageUrl(task, sample) {\n  if (!task || !sample?.image_path) return "";\n  const base = task.path.replace(/\\/data\\.json$/, "");\n  return `../${base}/${sample.image_path}`.replaceAll("\\\\", "/");\n}',
        'function sampleImageUrl(task, sample) {\n  const row = yzrRowsForTask(task)[0];\n  return row ? `../yzrcheck/${row.case_dir}/p0.png` : "";\n}',
    )
    app = app.replace("../yzrcheck", "../audit_cases").replace("YZR", "Audit")
    if 'tasks_180.json' not in app or 'process_gpt55.jsonl' not in app:
        raise RuntimeError('viewer patch did not apply')
    return app


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename in ("index.html", "styles.css"):
        shutil.copy2(SOURCE_VIEWER / filename, OUTPUT / filename)
    (OUTPUT / "app.js").write_text(replacement_app(), encoding="utf-8")

    copied_check = OUTPUT / "audit_cases"
    copied_check.mkdir(exist_ok=True)
    shutil.copy2(SOURCE_CHECK / "index.csv", copied_check / "index.csv")
    for case in SOURCE_CHECK.iterdir():
        if case.is_dir() and case.name[:3].isdigit() and not (copied_check / case.name).exists():
            shutil.copytree(case, copied_check / case.name)

    rows = check_rows()
    keys = {row["task_key"] for row in rows}
    task_rows = []
    for task in load_json(ROOT / "json" / "tasks_see2thinkbench_1200task_available.json"):
        rel = task["path"].replace("annotation/dataset/data/", "").removesuffix("/data.json")
        key = f"{rel}::{int(task['id'])}"
        if key in keys:
            first = next(row for row in rows if row["task_key"] == key)
            question = (SOURCE_CHECK / first["case_dir"] / "q.md").read_text(encoding="utf-8")
            task_rows.append({**task, "question": question})
    data = OUTPUT / "data"
    data.mkdir(exist_ok=True)
    (data / "tasks_180.json").write_text(json.dumps(task_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (data / "empty.jsonl").write_text("", encoding="utf-8")
    (data / "empty.csv").write_text("case_index\n", encoding="utf-8")
    shutil.copy2(ROOT / "prompt" / "see2think_vaot_full.txt", data / "see2think_vaot_full.txt")

    for model, tag in MODELS:
        process, key_steps, answers = [], [], []
        for row in rows:
            if row["model"] != model:
                continue
            meta = load_json(SOURCE_CHECK / row["case_dir"] / "metadata.json")
            judge = {}
            for metric in ("action_relevance", "render_faithfulness", "feedback_uptake"):
                judge[metric] = score(float(meta[metric])) | {"reason": meta.get(f"{metric}_reason", "")}
            judge["summary"] = "Human-validation case; assess the four displayed judge decisions."
            process.append({"status": "ok", "task_key": row["task_key"], "model": model, "setting": "full", "judge": judge})
            key_steps.append({"status": "ok", "task_key": row["task_key"], "key_steps": [meta.get("key_step_id")], "reason": meta.get("key_step_reason", ""), "no_valid_visual_step": False})
            answers.append({"status": "ok", "task_key": row["task_key"], "correct": bool(meta.get("full_correct")), "final_answer": meta.get("full_answer", "")})
        write_jsonl(data / f"process_{tag}.jsonl", process)
        write_jsonl(data / f"key_{tag}.jsonl", key_steps)
        write_jsonl(data / f"answer_{tag}.jsonl", answers)

    (OUTPUT / "README.md").write_text(
        "# See2Think 人工审计：原版轨迹查看器（180 条）\n\n"
        "这个包保留项目原有的 See2Think 轨迹查看器界面和标注交互，只包含人工审计的 180 个模型-任务案例。\n\n"
        "## 使用方法\n\n"
        "1. 完整解压 ZIP。\n2. 双击 `START_ANNOTATION.bat`。\n3. 浏览器打开 `http://127.0.0.1:8769/`。\n"
        "4. 左侧 **候选集** 保持在 `Human audit 180`。\n5. 每条的四项（关键步骤选择、动作相关性、忠诚度、反馈采纳）选择：合理 / 部分合理 / 不合理。\n"
        "6. 在顶部 Summary 区域导出 JSON 或 CSV，发送给项目负责人。\n\n"
        "标注自动存于当前浏览器。关闭浏览器或清缓存前务必导出。运行时请保持启动脚本的命令窗口打开。\n",
        encoding="utf-8",
    )
    (OUTPUT / "START_ANNOTATION.bat").write_text(
        '@echo off\ncd /d "%~dp0"\nstart "" /b python -m http.server 8769\ntimeout /t 2 /nobreak >nul\nstart "See2Think audit" http://127.0.0.1:8769/\necho Audit server is running. Keep this window open.\npause\n',
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(OUTPUT), "zip", root_dir=OUTPUT)
    print(f"package={OUTPUT}\nzip={archive}\ntasks={len(task_rows)}\ncases={len(rows)}")


if __name__ == "__main__":
    main()
