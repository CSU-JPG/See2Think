import json
import shutil
from collections import defaultdict
from pathlib import Path

STAMP = "20260725_150902"

# 每种转换方向抽 5 条，共 10 条
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

# 原始完整轨迹根目录
FULL_RESULTS_ROOT = Path("newtasks/final1200_qwen3-vl-32b-instruct_vaot_full_floor")
WRONG_RESULTS_ROOT = Path("newtasks/final1200_qwen3-vl-32b-instruct_vaot_wrong_render_floor")

OUT_ROOT = Path("outputs/qwen_transition_full_cases_10")
ZIP_BASE = Path("outputs/qwen_transition_full_cases_10")

# 优先选择最有分析价值的类别
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


def find_trajectory_dir(root: Path, row: dict):
    """
    优先使用 relative_source_dir。
    如果找不到，再根据 source 和 sample_id 搜索。
    """

    relative_dir = row.get("relative_source_dir")

    candidates = []

    if relative_dir:
        relative_path = Path(str(relative_dir))

        candidates.extend([
            root / relative_path,
            relative_path,
        ])

    source = str(row.get("source", "")).strip()
    sample_id = str(row.get("sample_id", "")).strip()

    if source and sample_id:
        candidates.extend([
            root / source / sample_id,
            root / source / safe_name(sample_id),
        ])

    # 先检查直接候选
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()

    # 根据 steps.md 递归搜索
    if sample_id:
        possible_dirs = []

        for steps_file in root.rglob("steps.md"):
            parent = steps_file.parent

            if parent.name == sample_id:
                possible_dirs.append(parent)

        if len(possible_dirs) == 1:
            return possible_dirs[0].resolve()

        # 再结合 source 路径筛选
        if source:
            source_normalized = source.replace("\\", "/").lower()

            filtered = [
                path
                for path in possible_dirs
                if source_normalized
                in str(path).replace("\\", "/").lower()
            ]

            if len(filtered) == 1:
                return filtered[0].resolve()

    return None


def choose_balanced(grouped, priority, count):
    """
    优先从不同类别各抽一条，避免十条全来自同一个类别。
    """

    selected = []
    used_keys = set()

    # 第一轮：优先类别各取一条
    for task in priority:
        rows = grouped.get(task, [])

        if rows:
            item = rows[0]

            if item[0] not in used_keys:
                selected.append(item)
                used_keys.add(item[0])

        if len(selected) >= count:
            return selected

    # 第二轮：从全部类别补足
    for task in sorted(grouped):
        for item in grouped[task]:
            if item[0] in used_keys:
                continue

            selected.append(item)
            used_keys.add(item[0])

            if len(selected) >= count:
                return selected

    return selected


def bool_correct(row):
    return bool(row.get("correct"))


def text_value(row, key):
    value = row.get(key, "")
    return "" if value is None else str(value)


full_rows = load_jsonl(FULL_ANSWER_FILE)
wrong_rows = load_jsonl(WRONG_ANSWER_FILE)

common_keys = sorted(set(full_rows) & set(wrong_rows))

correct_to_wrong = defaultdict(list)
wrong_to_correct = defaultdict(list)

for key in common_keys:
    full_row = full_rows[key]
    wrong_row = wrong_rows[key]

    full_correct = bool_correct(full_row)
    wrong_correct = bool_correct(wrong_row)

    task = (
        full_row.get("target_task")
        or wrong_row.get("target_task")
        or "UNKNOWN"
    )

    item = (key, full_row, wrong_row)

    if full_correct and not wrong_correct:
        correct_to_wrong[task].append(item)

    elif not full_correct and wrong_correct:
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


# 删除旧输出，避免混入之前的文件
if OUT_ROOT.exists():
    shutil.rmtree(OUT_ROOT)

OUT_ROOT.mkdir(parents=True, exist_ok=True)

main_readme = [
    "# Qwen VAoT / WrongRender 完整轨迹人工检查样本",
    "",
    f"- 总样本数：{sum(len(x[2]) for x in selected_groups)}",
    f"- VAoT 对 → WrongRender 错：{len(selected_correct_to_wrong)}",
    f"- VAoT 错 → WrongRender 对：{len(selected_wrong_to_correct)}",
    "",
    "每个 case 文件夹包含：",
    "",
    "- `vaot_full/`：正常 VAoT 的完整原始轨迹",
    "- `wrong_render/`：WrongRender 的完整原始轨迹",
    "- `case_summary.md`：题目、答案、判分结果及人工分析模板",
    "",
]

copied_count = 0
missing_cases = []

case_global_index = 0

for group_dir_name, direction_name, items in selected_groups:
    group_dir = OUT_ROOT / group_dir_name
    group_dir.mkdir(parents=True, exist_ok=True)

    main_readme.extend([
        f"## {direction_name}",
        "",
    ])

    for local_index, (task_key, full_row, wrong_row) in enumerate(items, 1):
        case_global_index += 1

        task = (
            full_row.get("target_task")
            or wrong_row.get("target_task")
            or "UNKNOWN"
        )

        case_name = (
            f"case_{case_global_index:02d}_"
            f"{safe_name(task)}_"
            f"{safe_name(task_key)}"
        )

        case_dir = group_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)

        full_source_dir = find_trajectory_dir(
            FULL_RESULTS_ROOT,
            full_row,
        )

        wrong_source_dir = find_trajectory_dir(
            WRONG_RESULTS_ROOT,
            wrong_row,
        )

        copy_status = []

        # 复制正常 VAoT 完整目录
        if full_source_dir:
            full_target = case_dir / "vaot_full"

            shutil.copytree(
                full_source_dir,
                full_target,
                dirs_exist_ok=True,
            )

            copy_status.append(
                f"- VAoT 完整目录：已复制\n"
                f"  - 来源：`{full_source_dir}`"
            )
        else:
            copy_status.append(
                "- VAoT 完整目录：**未找到**"
            )

        # 复制 WrongRender 完整目录
        if wrong_source_dir:
            wrong_target = case_dir / "wrong_render"

            shutil.copytree(
                wrong_source_dir,
                wrong_target,
                dirs_exist_ok=True,
            )

            copy_status.append(
                f"- WrongRender 完整目录：已复制\n"
                f"  - 来源：`{wrong_source_dir}`"
            )
        else:
            copy_status.append(
                "- WrongRender 完整目录：**未找到**"
            )

        if full_source_dir and wrong_source_dir:
            copied_count += 1
        else:
            missing_cases.append(task_key)

        summary_lines = [
            f"# Case {case_global_index:02d}",
            "",
            f"- **转换方向**：{direction_name}",
            f"- **类别**：{task}",
            f"- **Task key**：`{task_key}`",
            f"- **Source**：`{text_value(full_row, 'source')}`",
            f"- **Sample ID**：`{text_value(full_row, 'sample_id')}`",
            "",
            "## 文件复制状态",
            "",
            *copy_status,
            "",
            "## Question",
            "",
            text_value(full_row, "question"),
            "",
            "## Ground Truth",
            "",
            text_value(full_row, "ground_truth"),
            "",
            "## VAoT-Full",
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
            "请同时打开：",
            "",
            "- `vaot_full/steps.md`",
            "- `wrong_render/steps.md`",
            "- 两个目录中的原图及各轮渲染图",
            "",
            "填写：",
            "",
            "1. 正常 VAoT 请求了什么视觉操作？",
            "2. 正常渲染是否正确执行？",
            "3. WrongRender 具体改错了什么？",
            "4. 模型后续是否明确引用了渲染结果？",
            "5. 最终答案为什么发生变化？",
            "6. 属于下列哪种情况？",
            "",
            "   - 被错误反馈带偏",
            "   - 错误反馈偶然纠偏",
            "   - 模型忽略了渲染反馈",
            "   - 模型发现并抵抗了错误反馈",
            "   - 多一轮推理导致答案改变",
            "   - 最终答案措辞或 judge 波动",
            "   - 其他",
            "",
            "### 人工结论",
            "",
            "",
        ]

        (case_dir / "case_summary.md").write_text(
            "\n".join(summary_lines),
            encoding="utf-8",
        )

        main_readme.extend([
            f"### Case {case_global_index:02d}：{task}",
            "",
            f"- Task key：`{task_key}`",
            f"- 文件夹：`{group_dir_name}/{case_name}`",
            "",
        ])


main_readme.extend([
    "## 复制检查",
    "",
    f"- 两边完整轨迹均成功复制：{copied_count} / 10",
    f"- 未完整找到的样本数：{len(missing_cases)}",
])

if missing_cases:
    main_readme.extend([
        "",
        "未完整找到的 Task key：",
        "",
    ])

    for key in missing_cases:
        main_readme.append(f"- `{key}`")

(OUT_ROOT / "README.md").write_text(
    "\n".join(main_readme),
    encoding="utf-8",
)

# 创建 ZIP
zip_path = shutil.make_archive(
    str(ZIP_BASE),
    "zip",
    root_dir=OUT_ROOT,
)

print("")
print("========================================")
print("完整样本抽取完成")
print("========================================")
print(f"输出文件夹：{OUT_ROOT}")
print(f"ZIP 文件：{zip_path}")
print(f"完整复制成功：{copied_count}/10")

if missing_cases:
    print("")
    print("以下样本有目录未找到：")

    for key in missing_cases:
        print(f"  {key}")

