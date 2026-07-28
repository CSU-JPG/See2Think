import json
import re
import argparse
import os
import glob
from pathlib import Path

PREFIX = "annotation/dataset/data/"

DATASET = [
    "math",
    "m3cot/test0",
    "m3cot/test1",
    "clevr_math/val",
]

def read_indices(indices_patterns):
    """
    支持多个索引文件和通配符模式
    """
    all_indices = set()  # 使用set避免重复

    for pattern in indices_patterns:
        # 如果包含通配符，使用glob匹配
        if '*' in pattern or '?' in pattern:
            matched_files = glob.glob(pattern)
            if not matched_files:
                print(f"Warning: No files found matching pattern: {pattern}")
                continue
            for file_path in matched_files:
                print(f"Reading indices from: {file_path}")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_indices = [int(line.strip()) for line in f.readlines()]
                        all_indices.update(file_indices)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
        else:
            # 单个文件路径
            if os.path.exists(pattern):
                print(f"Reading indices from: {pattern}")
                try:
                    with open(pattern, "r", encoding="utf-8") as f:
                        file_indices = [int(line.strip()) for line in f.readlines()]
                        all_indices.update(file_indices)
                except Exception as e:
                    print(f"Error reading {pattern}: {e}")
            else:
                print(f"Warning: Index file not found: {pattern}")

    # 转换为排序列表
    sorted_indices = sorted(list(all_indices))
    print(f"Total unique indices loaded: {len(sorted_indices)}")
    if sorted_indices:
        print(f"Indices range: {sorted_indices[0]} to {sorted_indices[-1]}")
    return sorted_indices

def create_tasks(json_path, indices):
    tasks = []
    if len(indices) == 0:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        indices = list(range(len(data)))
    for order, i in enumerate(indices):
        task = {
            "order": order,
            "path": json_path,
            "id": i,
        }
        tasks.append(task)
    return tasks


def save_tasks(tasks, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    print(f"Tasks saved to {save_path}")

if __name__ == "__main__":
    """
    examples:
    # 单个索引文件
    python3 create_tasks.py --dataset math --indices file1.idx --save_path tasks/math_tasks.json

    # 多个索引文件
    python3 create_tasks.py --dataset math --indices file1.idx file2.idx file3.idx --save_path tasks/math_tasks.json

    # 通配符模式
    python3 create_tasks.py --dataset math --indices "tasks/check_question/clevr_math/*.idx" --save_path tasks/math_tasks.json

    # 混合模式：多个文件和通配符
    python3 create_tasks.py --dataset math --indices file1.idx "tasks/check_question/clevr_math/*.idx" file2.idx --save_path tasks/math_tasks.json
    """
    parser = argparse.ArgumentParser(description="Create tasks for datasets")
    parser.add_argument("--dataset", type=str, choices=DATASET, help="数据集的json文件路径")
    parser.add_argument("--indices", type=str, nargs='+', help="任务索引文件路径，支持多个文件和通配符模式，例如：--indices file1.idx tasks/check_question/clevr_math/*.idx")
    parser.add_argument("--save_path", type=str, help="任务保存路径")
    args = parser.parse_args()

    json_path = f"{PREFIX}{args.dataset}/data.json"
    indices = read_indices(args.indices) if args.indices else []
    tasks = create_tasks(json_path, indices)
    save_path = (
        args.save_path
        if args.save_path
        else f"tasks/{args.dataset.replace('/', '_')}_tasks.json"
    )  
    save_tasks(tasks, save_path)