import json
import shutil
from collections import defaultdict
from pathlib import Path

STAMP = "20260725_150902"
N_PER_DIRECTION = 5

ANSWER_ROOT = Path("eval/results")

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

OUT_ROOT = Path("outputs/qwen_transition_cases_10_light")

CORRECT_TO_WRONG_PRIORITY = [
    "Clevr",
    "SuperClevr",
    "Math-智力",
    "Commonsense",
    "IntPhys2",
    "真实具身数据",
]

WRONG_TO_CORRECT_PRIORITY = [
    "IntPhys2",
    "真实具身数据",
    "Prism",
    "Science",
    "Physics",
    "Math-几何",
]

# 只复制这些人工检查常用文件
ALLOWED_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

# 明显不需要的目录
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "cache",
    "caches",
    "logs",
    "tmp",
    "temp",
}

# 单个文件超过这个大小就跳过，避免误复制超大文件
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB


def load_jsonl(path: Path):
    rows = {}

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"跳过无效 JSON：{path}:{line_number}: {exc}")
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


def bool_correct(row):
    return bool(row.get("correct"))


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

            if item[0] not in used:
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
    relative_dir = row.get("relative_source_dir")

    if relative_dir:
        candidate = root / Path(str(relative_dir))

        if candidate.exists() and candidate.is_dir():
            return candidate

    source = str(row.get("source", "")).strip()
    sample_id = str(row.get("sample_id", "")).strip()

    matches = []

    for steps_file in root.rglob("steps.md"):
        parent = steps_file.parent

        if parent.name != sample_id:
            continue

        if source:
            normalized_source = source.replace("\\", "/").lower()
            normalized_path = str(parent).replace("\\", "/").lower()

            if normalized_source not in normalized_path:
                continue

        matches.append(parent)

    if len(matches) == 1:
        return matches[0]

    if matches:
        return matches[0]

    return None


def should_copy_file(path: Path):
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False

    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return False
    except OSError:
        return False

    return True


def copy_lightweight_tree(source: Path, target: Path):
    copied = 0
    skipped_large = 0

    for path in source.rglob("*"):
        relative = path.relative_to(source)

        if any(part.lower() in SKIP_DIR_NAMES for part in relative.parts):
            continue

        if not path.is_file():
            continue

        if not should_copy_file(path):
            try:
                if path.stat().st_size > MAX_FILE_SIZE:
                    skipped_large += 1
            except OSError:
                pass
            continue

        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied += 1

    return copied, skipped_large


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

    if bool_correct(full_row) and not bool_correct(wrong_row):
        correct_to_wrong[task].append(item)

    elif not bool_correct(full_row) and bool_correct(wrong_row):
        wrong_to_correct[task].append(item)


selected_correct_to_wrong = choose_balanced(
    correct_to_wrong,
    CORRECT_TO_WRONG_PRIORITY,
    N_PER_DIRECTION,
)

selected_wrong_to_correct = choose_balanced(
    wrong_to_correct,
    WRONG_TO_CORRECT_PRIORITY,
    N_PER_DIRECTION,
)

selected_groups = [
    (
        "01_correct_to_wrong",
        "VAoT 对 → WrongRender 错",
        selected_correct_to_wrong,
    ),
    (
        "02_wrong_to_correct",
        "VAoT 错 → WrongRender 对",
        selected_wrong_to_correct,
    ),
]

if OUT_ROOT.exists():
    shutil.rmtree(OUT_ROOT)

OUT_ROOT.mkdir(parents=True, exist_ok=True)

readme = [
    "# Qwen VAoT / WrongRender 人工检查样本",
    "",
    "- 共 10 条",
    "- VAoT 对 → WrongRender 错：5 条",
    "- VAoT 错 → WrongRender 对：5 条",
    "",
    "每条只保留人工检查需要的 Markdown、JSON 和图片。",
    "",
]

success_count = 0
case_index = 0

for group_dir_name, direction_name, items in selected_groups:
    group_dir = OUT_ROOT / group_dir_name
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

        full_status = "未找到"
        wrong_status = "未找到"

        if full_source:
            copied, skipped = copy_lightweight_tree(
                full_source,
                case_dir / "vaot_full",
            )

            full_status = (
                f"已复制 {copied} 个文件，"
                f"跳过超大文件 {skipped} 个"
            )

        if wrong_source:
            copied, skipped = copy_lightweight_tree(
                wrong_source,
                case_dir / "wrong_render",
            )

            wrong_status = (
                f"已复制 {copied} 个文件，"
                f"跳过超大文件 {skipped} 个"
            )

        if full_source and wrong_source:
            success_count += 1

        summary = [
            f"# Case {case_index:02d}",
            "",
            f"- 转换方向：{direction_name}",
            f"- 类别：{task}",
            f"- Task key：`{task_key}`",
            f"- Source：`{text_value(full_row, 'source')}`",
            f"- Sample ID：`{text_value(full_row, 'sample_id')}`",
            "",
            "## 复制状态",
            "",
            f"- VAoT：{full_status}",
            f"- WrongRender：{wrong_status}",
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
            "1. WrongRender 改错了什么？",
            "2. 模型是否使用了错误反馈？",
            "3. 为什么发生对→错或错→对？",
            "4. 属于偶然纠偏、被带偏、忽略反馈、额外推理还是判分波动？",
            "",
        ]

        (case_dir / "case_summary.md").write_text(
            "\n".join(summary),
            encoding="utf-8",
        )

        readme.extend([
            f"## Case {case_index:02d}",
            "",
            f"- 方向：{direction_name}",
            f"- 类别：{task}",
            f"- Task key：`{task_key}`",
            f"- 路径：`{group_dir_name}/{case_name}`",
            "",
        ])

(OUT_ROOT / "README.md").write_text(
    "\n".join(readme),
    encoding="utf-8",
)

print("")
print("========================================")
print("轻量版 10 条样本已生成")
print("========================================")
print(f"输出目录：{OUT_ROOT}")
print(f"成功找到双侧轨迹：{success_count}/10")
print("未生成 ZIP")
