import csv
import json
from collections import defaultdict
from pathlib import Path

STAMP = "20260725_150902"
N_EACH_DIRECTION = 12

ROOT = Path("neweval/results")

FULL_PATH = (
    ROOT
    / f"answer_qwen3vl32b_1200_{STAMP}_vaot_full"
    / "answer_judge.jsonl"
)

WRONG_PATH = (
    ROOT
    / f"answer_qwen3vl32b_1200_{STAMP}_vaot_wrong_render"
    / "answer_judge.jsonl"
)

OUT_DIR = Path("outputs/qwen_transition_review")
OUT_MD = OUT_DIR / "transition_samples.md"
OUT_CSV = OUT_DIR / "transition_samples.csv"

# 优先抽这些最有分析价值的类别
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

def make_key(row):
    key = row.get("task_key")
    if key:
        return str(key)

    return (
        f"{row.get('source', '')}::"
        f"{row.get('sample_id', '')}"
    )

def load_jsonl(path):
    result = {}

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

            result[make_key(row)] = row

    return result

def transition_type(full_row, wrong_row):
    full_correct = bool(full_row.get("correct"))
    wrong_correct = bool(wrong_row.get("correct"))

    if full_correct and not wrong_correct:
        return "correct_to_wrong"

    if not full_correct and wrong_correct:
        return "wrong_to_correct"

    return None

def select_balanced(grouped, priority, total):
    selected = []
    used = set()

    # 第一轮：优先类别每类先抽 1 条
    for task in priority:
        candidates = grouped.get(task, [])
        if candidates:
            item = candidates[0]
            selected.append(item)
            used.add(item[0])

            if len(selected) >= total:
                return selected

    # 第二轮：优先类别继续轮流补充
    round_index = 1

    while len(selected) < total:
        added = False

        for task in priority:
            candidates = grouped.get(task, [])

            if round_index < len(candidates):
                item = candidates[round_index]

                if item[0] not in used:
                    selected.append(item)
                    used.add(item[0])
                    added = True

                if len(selected) >= total:
                    return selected

        if not added:
            break

        round_index += 1

    # 第三轮：从全部剩余样本中补满
    for task in sorted(grouped):
        for item in grouped[task]:
            if item[0] in used:
                continue

            selected.append(item)
            used.add(item[0])

            if len(selected) >= total:
                return selected

    return selected

def value(row, field):
    v = row.get(field, "")
    if v is None:
        return ""
    return str(v)

full_rows = load_jsonl(FULL_PATH)
wrong_rows = load_jsonl(WRONG_PATH)

common_keys = sorted(set(full_rows) & set(wrong_rows))

correct_to_wrong = defaultdict(list)
wrong_to_correct = defaultdict(list)

for key in common_keys:
    full_row = full_rows[key]
    wrong_row = wrong_rows[key]

    change = transition_type(full_row, wrong_row)
    if not change:
        continue

    task = (
        full_row.get("target_task")
        or wrong_row.get("target_task")
        or "UNKNOWN"
    )

    item = (key, full_row, wrong_row)

    if change == "correct_to_wrong":
        correct_to_wrong[task].append(item)
    elif change == "wrong_to_correct":
        wrong_to_correct[task].append(item)

selected_correct_to_wrong = select_balanced(
    correct_to_wrong,
    CORRECT_TO_WRONG_PRIORITY,
    N_EACH_DIRECTION,
)

selected_wrong_to_correct = select_balanced(
    wrong_to_correct,
    WRONG_TO_CORRECT_PRIORITY,
    N_EACH_DIRECTION,
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

all_selected = [
    ("VAoT 对 → WrongRender 错", "correct_to_wrong", selected_correct_to_wrong),
    ("VAoT 错 → WrongRender 对", "wrong_to_correct", selected_wrong_to_correct),
]

md = [
    "# Qwen VAoT 与 WrongRender 转换样本",
    "",
    f"- VAoT 文件：`{FULL_PATH}`",
    f"- WrongRender 文件：`{WRONG_PATH}`",
    f"- 对齐样本数：{len(common_keys)}",
    f"- 每种方向抽样数：{N_EACH_DIRECTION}",
    "",
]

csv_rows = []

for section_title, direction, items in all_selected:
    md.extend([
        f"# {section_title}",
        "",
    ])

    for index, (key, full_row, wrong_row) in enumerate(items, 1):
        task = (
            full_row.get("target_task")
            or wrong_row.get("target_task")
            or "UNKNOWN"
        )

        source = full_row.get("source") or wrong_row.get("source") or ""
        sample_id = (
            full_row.get("sample_id")
            or wrong_row.get("sample_id")
            or ""
        )

        relative_full = value(full_row, "relative_source_dir")
        relative_wrong = value(wrong_row, "relative_source_dir")

        md.extend([
            f"## {index}. {task}",
            "",
            f"- **转换方向**：{section_title}",
            f"- **Task key**：`{key}`",
            f"- **Source**：`{source}`",
            f"- **Sample ID**：`{sample_id}`",
            f"- **VAoT 相对目录**：`{relative_full}`",
            f"- **WrongRender 相对目录**：`{relative_wrong}`",
            "",
            "### Question",
            "",
            value(full_row, "question"),
            "",
            "### Ground Truth",
            "",
            value(full_row, "ground_truth"),
            "",
            "### VAoT final answer",
            "",
            value(full_row, "final_answer"),
            "",
            "### VAoT judge reason",
            "",
            value(full_row, "reason"),
            "",
            "### WrongRender final answer",
            "",
            value(wrong_row, "final_answer"),
            "",
            "### WrongRender judge reason",
            "",
            value(wrong_row, "reason"),
            "",
            "### 人工分析",
            "",
            "- WrongRender 修改了什么：",
            "- 模型是否引用了错误视觉反馈：",
            "- 答案变化的直接原因：",
            "- 初步归类：偶然纠偏 / 被错误反馈带偏 / 忽略反馈 / 额外推理 / 判分波动 / 其他",
            "",
            "---",
            "",
        ])

        csv_rows.append({
            "direction": direction,
            "target_task": task,
            "task_key": key,
            "source": source,
            "sample_id": sample_id,
            "full_relative_source_dir": relative_full,
            "wrong_relative_source_dir": relative_wrong,
            "question": value(full_row, "question"),
            "ground_truth": value(full_row, "ground_truth"),
            "full_answer": value(full_row, "final_answer"),
            "full_reason": value(full_row, "reason"),
            "wrong_answer": value(wrong_row, "final_answer"),
            "wrong_reason": value(wrong_row, "reason"),
        })

OUT_MD.write_text("\n".join(md), encoding="utf-8")

with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
    fieldnames = list(csv_rows[0].keys())
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"已生成：{OUT_MD}")
print(f"已生成：{OUT_CSV}")

print("\nVAoT 对 → WrongRender 错：")
for key, full_row, wrong_row in selected_correct_to_wrong:
    print(
        f"  {full_row.get('target_task', ''):16s} "
        f"{key}"
    )

print("\nVAoT 错 → WrongRender 对：")
for key, full_row, wrong_row in selected_wrong_to_correct:
    print(
        f"  {full_row.get('target_task', ''):16s} "
        f"{key}"
    )
