import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

STAMP = "20260725_150902"
N_PER_DIRECTION = 5

ANSWER_ROOT = Path("neweval/results")

FULL_ANSWER_FILE = (
    ANSWER_ROOT
    / f"answer_qwen3vl32b_1200_{STAMP}_vaot_full"
    / "answer_judge.jsonl"
)

WRONG_ANSWER_FILE = (
    ANSWER_ROOT
    / f"answer_qwen3vl32b_1200_{STAMP}_vaot_wrong_render"
    / "answer_judge.jsonl"
)

FULL_RESULTS_ROOT = Path(
    "newtasks/final1200_qwen3-vl-32b-instruct_vaot_full_floor"
)

WRONG_RESULTS_ROOT = Path(
    "newtasks/final1200_qwen3-vl-32b-instruct_vaot_wrong_render_floor"
)

OUT_ROOT = Path("outputs/qwen_transition_cases_10_minimal")

CORRECT_TO_WRONG_PRIORITY = [
    "Clevr",
    "SuperClevr",
    "Math-智力",
    "Commonsense",
    "IntPhys2",
]

WRONG_TO_CORRECT_PRIORITY = [
    "IntPhys2",
    "真实具身数据",
    "Prism",
    "Science",
    "Physics",
]

# 只额外保留这些小型结构文件
OPTIONAL_METADATA_NAMES = {
    "result.json",
    "results.json",
    "metadata.json",
    "trajectory.json",
    "task.json",
    "answer.json",
    "actions.json",
    "response.json",
    "config.json",
}

MAX_METADATA_SIZE = 2 * 1024 * 1024
MAX_IMAGE_SIZE = 20 * 1024 * 1024


def load_jsonl(path: Path):
    rows = {}

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"跳过无效 JSON：{path}:{line_no}: {exc}")
                continue

            key = row.get("task_key")

            if not key:
                key = (
                    f"{row.get('source', '')}::"
                    f"{row.get('sample_id', '')}"
                )

            rows[str(key)] = row

    return rows


def safe_name(text):
    return (
        str(text)
        .replace("/", "__")
        .replace("\\", "__")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


def text_value(row, key):
    value = row.get(key, "")
    return "" if value is None else str(value)


def choose_balanced(grouped, priority, count):
    selected = []
    used = set()

    for task in priority:
        items = grouped.get(task, [])

        if items:
            item = items[0]
            selected.append(item)
            used.add(item[0])

        if len(selected) >= count:
            return selected

    for task in sorted(grouped):
        for item in grouped[task]:
            if item[0] in used:
                continue

            selected.append(item)
            used.add(item[0])

            if len(selected) >= count:
                return selected

    return selected


def find_trajectory_dir(root: Path, row: dict):
    """
    根据 task_key 精确定位轨迹目录。

    例如：
    super_clevr::11
    -> root/super_clevr/**/11/steps.md

    clevr_math/val::0
    -> root/clevr_math/val/**/0/steps.md
    """

    task_key = str(row.get("task_key", "")).strip()

    if "::" in task_key:
        source_key, sample_id = task_key.rsplit("::", 1)
    else:
        source_key = str(row.get("source", "")).strip()
        sample_id = str(row.get("sample_id", "")).strip()

    source_key = source_key.replace("\\", "/").strip("/")
    sample_id = sample_id.strip()

    if not source_key or not sample_id:
        print(f"task_key 信息不完整：{task_key}")
        return None

    source_root = root / Path(source_key)

    if not source_root.exists():
        print(
            f"数据集目录不存在：task_key={task_key}\n"
            f"  尝试目录：{source_root}"
        )
        return None

    matches = [
        steps_file.parent
        for steps_file in source_root.rglob("steps.md")
        if steps_file.parent.name == sample_id
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        print(
            f"发现多个匹配，默认选择第一个："
            f"task_key={task_key}"
        )

        for match in matches:
            print(f"  候选：{match}")

        return matches[0]

    print(
        f"未找到轨迹：task_key={task_key}\n"
        f"  数据集根目录：{source_root}\n"
        f"  样本编号：{sample_id}"
    )

    return None

def extract_referenced_paths(markdown_text: str):
    references = set()

    # Markdown 图片或链接：
    # ![...](path)
    # [...](path)
    markdown_pattern = r'!?\[[^\]]*\]\(([^)]+)\)'

    for match in re.findall(markdown_pattern, markdown_text):
        value = match.strip().strip('"').strip("'")

        # 去掉可选标题，例如 image.png "caption"
        if " " in value:
            first = value.split(" ", 1)[0]
            if first.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".gif")
            ):
                value = first

        references.add(unquote(value))

    # HTML 图片：
    # <img src="path">
    html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'

    for match in re.findall(
        html_pattern,
        markdown_text,
        flags=re.IGNORECASE,
    ):
        references.add(unquote(match.strip()))

    # 裸路径，例如某些 steps.md 直接写：
    # render_01.png
    bare_pattern = (
        r'(?<![\w/.-])'
        r'([A-Za-z0-9_./\\-]+'
        r'\.(?:png|jpg|jpeg|webp|gif))'
    )

    for match in re.findall(
        bare_pattern,
        markdown_text,
        flags=re.IGNORECASE,
    ):
        references.add(unquote(match.strip()))

    return references


def resolve_reference(source_dir: Path, reference: str):
    reference = reference.strip()

    if reference.startswith(("http://", "https://", "data:")):
        return None

    reference = reference.replace("\\", "/")
    reference = reference.split("#", 1)[0]
    reference = reference.split("?", 1)[0]

    candidate = source_dir / Path(reference)

    if candidate.exists() and candidate.is_file():
        return candidate

    # 若 Markdown 只写了文件名，则在当前样本目录内找同名文件
    filename = Path(reference).name

    matches = [
        path
        for path in source_dir.rglob(filename)
        if path.is_file()
    ]

    if len(matches) == 1:
        return matches[0]

    if matches:
        return matches[0]

    return None


def copy_minimal_case(source_dir: Path, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)

    steps_file = source_dir / "steps.md"

    copied_files = []
    missing_references = []

    if not steps_file.exists():
        return copied_files, ["steps.md 不存在"]

    target_steps = target_dir / "steps.md"
    shutil.copy2(steps_file, target_steps)
    copied_files.append("steps.md")

    # 额外复制 q.md
    q_file = source_dir / "q.md"
    if q_file.exists() and q_file.is_file():
        shutil.copy2(q_file, target_dir / "q.md")
        copied_files.append("q.md")

    # 额外复制 p0：兼容 p0 文件夹或 p0.* 图片文件
    p0_candidates = [
        source_dir / "p0",
        source_dir / "p0.png",
        source_dir / "p0.jpg",
        source_dir / "p0.jpeg",
        source_dir / "p0.webp",
    ]

    for p0_path in p0_candidates:
        if not p0_path.exists():
            continue

        if p0_path.is_file():
            shutil.copy2(
                p0_path,
                target_dir / p0_path.name,
            )
            copied_files.append(p0_path.name)
            break

        if p0_path.is_dir():
            p0_target = target_dir / "p0"
            p0_target.mkdir(parents=True, exist_ok=True)

            for path in p0_path.rglob("*"):
                if not path.is_file():
                    continue

                relative = path.relative_to(p0_path)
                destination = p0_target / relative
                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(path, destination)
                copied_files.append(
                    str(Path("p0") / relative)
                )

            break
    markdown_text = steps_file.read_text(
        encoding="utf-8",
        errors="replace",
    )

    references = extract_referenced_paths(markdown_text)

    for reference in sorted(references):
        source_file = resolve_reference(source_dir, reference)

        if source_file is None:
            missing_references.append(reference)
            continue

        try:
            if source_file.stat().st_size > MAX_IMAGE_SIZE:
                missing_references.append(
                    f"{reference}（超过 20 MB，已跳过）"
                )
                continue
        except OSError:
            missing_references.append(reference)
            continue

        try:
            relative = source_file.relative_to(source_dir)
        except ValueError:
            relative = Path("referenced_images") / source_file.name

        destination = target_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source_file, destination)
        copied_files.append(str(relative))

    # 仅复制样本根目录下少量必要 JSON，不递归
    for metadata_file in source_dir.iterdir():
        if not metadata_file.is_file():
            continue

        if metadata_file.name.lower() not in OPTIONAL_METADATA_NAMES:
            continue

        try:
            if metadata_file.stat().st_size > MAX_METADATA_SIZE:
                continue
        except OSError:
            continue

        destination = target_dir / metadata_file.name
        shutil.copy2(metadata_file, destination)
        copied_files.append(metadata_file.name)

    # 写复制清单
    manifest = [
        "# Minimal trajectory manifest",
        "",
        f"- 来源目录：`{source_dir}`",
        f"- 已复制文件数：{len(copied_files)}",
        f"- 未找到或跳过的引用数：{len(missing_references)}",
        "",
        "## 已复制文件",
        "",
    ]

    for item in copied_files:
        manifest.append(f"- `{item}`")

    if missing_references:
        manifest.extend([
            "",
            "## 未找到或跳过的引用",
            "",
        ])

        for item in missing_references:
            manifest.append(f"- `{item}`")

    (target_dir / "copy_manifest.md").write_text(
        "\n".join(manifest),
        encoding="utf-8",
    )

    return copied_files, missing_references


full_rows = load_jsonl(FULL_ANSWER_FILE)
wrong_rows = load_jsonl(WRONG_ANSWER_FILE)

common_keys = sorted(set(full_rows) & set(wrong_rows))

correct_to_wrong = defaultdict(list)
wrong_to_correct = defaultdict(list)

for key in common_keys:
    full_row = full_rows[key]
    wrong_row = wrong_rows[key]

    task = (
        full_row.get("target_task")
        or wrong_row.get("target_task")
        or "UNKNOWN"
    )

    item = (key, full_row, wrong_row)

    full_correct = bool(full_row.get("correct"))
    wrong_correct = bool(wrong_row.get("correct"))

    if full_correct and not wrong_correct:
        correct_to_wrong[task].append(item)

    elif not full_correct and wrong_correct:
        wrong_to_correct[task].append(item)


selected_groups = [
    (
        "01_correct_to_wrong",
        "VAoT 对 → WrongRender 错",
        choose_balanced(
            correct_to_wrong,
            CORRECT_TO_WRONG_PRIORITY,
            N_PER_DIRECTION,
        ),
    ),
    (
        "02_wrong_to_correct",
        "VAoT 错 → WrongRender 对",
        choose_balanced(
            wrong_to_correct,
            WRONG_TO_CORRECT_PRIORITY,
            N_PER_DIRECTION,
        ),
    ),
]

if OUT_ROOT.exists():
    shutil.rmtree(OUT_ROOT)

OUT_ROOT.mkdir(parents=True, exist_ok=True)

readme = [
    "# Qwen 对错转换人工抽查",
    "",
    "共 10 条：",
    "",
    "- VAoT 对 → WrongRender 错：5 条",
    "- VAoT 错 → WrongRender 对：5 条",
    "",
    "每侧轨迹只复制：",
    "",
    "- `steps.md`",
    "- `steps.md` 实际引用的图片",
    "- 少量必要 JSON",
    "- `copy_manifest.md`",
    "",
]

case_index = 0
success_count = 0

for group_name, direction, items in selected_groups:
    group_dir = OUT_ROOT / group_name
    group_dir.mkdir(parents=True, exist_ok=True)

    for task_key, full_row, wrong_row in items:
        case_index += 1

        task = (
            full_row.get("target_task")
            or wrong_row.get("target_task")
            or "UNKNOWN"
        )

        case_name = (
            f"case_{case_index:02d}_"
            f"{safe_name(task)}_"
            f"{safe_name(task_key)}"
        )

        case_dir = group_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)

        full_source = find_trajectory_dir(
            FULL_RESULTS_ROOT,
            full_row,
        )

        wrong_source = find_trajectory_dir(
            WRONG_RESULTS_ROOT,
            wrong_row,
        )

        full_count = 0
        wrong_count = 0

        if full_source:
            copied, _ = copy_minimal_case(
                full_source,
                case_dir / "vaot_full",
            )
            full_count = len(copied)

        if wrong_source:
            copied, _ = copy_minimal_case(
                wrong_source,
                case_dir / "wrong_render",
            )
            wrong_count = len(copied)

        if full_source and wrong_source:
            success_count += 1

        summary = [
            f"# Case {case_index:02d}",
            "",
            f"- 转换方向：{direction}",
            f"- 类别：{task}",
            f"- Task key：`{task_key}`",
            f"- Source：`{text_value(full_row, 'source')}`",
            f"- Sample ID：`{text_value(full_row, 'sample_id')}`",
            f"- VAoT 已复制文件数：{full_count}",
            f"- WrongRender 已复制文件数：{wrong_count}",
            "",
            "## Question",
            "",
            text_value(full_row, "question"),
            "",
            "## Ground Truth",
            "",
            text_value(full_row, "ground_truth"),
            "",
            "## VAoT",
            "",
            f"- Correct：`{text_value(full_row, 'correct')}`",
            "",
            "### Final answer",
            "",
            text_value(full_row, "final_answer"),
            "",
            "### Judge reason",
            "",
            text_value(full_row, "reason"),
            "",
            "## WrongRender",
            "",
            f"- Correct：`{text_value(wrong_row, 'correct')}`",
            "",
            "### Final answer",
            "",
            text_value(wrong_row, "final_answer"),
            "",
            "### Judge reason",
            "",
            text_value(wrong_row, "reason"),
            "",
            "## 人工分析",
            "",
            "1. WrongRender 改错了哪个目标、位置、关系或标注？",
            "2. 模型后续是否明确使用了错误视觉状态？",
            "3. 答案改变来自视觉反馈，还是额外推理或措辞变化？",
            "4. 归类：被带偏 / 偶然纠偏 / 忽略反馈 / 抵抗反馈 / 判分波动 / 其他。",
            "",
        ]

        (case_dir / "case_summary.md").write_text(
            "\n".join(summary),
            encoding="utf-8",
        )

        readme.extend([
            f"## Case {case_index:02d}",
            "",
            f"- {direction}",
            f"- {task}",
            f"- `{task_key}`",
            f"- `{group_name}/{case_name}`",
            "",
        ])

(OUT_ROOT / "README.md").write_text(
    "\n".join(readme),
    encoding="utf-8",
)

print("")
print("========================================")
print("极简版 10 条样本已生成")
print("========================================")
print(f"输出目录：{OUT_ROOT}")
print(f"成功找到双侧轨迹：{success_count}/10")
print("只复制 steps.md 实际引用的图片")


