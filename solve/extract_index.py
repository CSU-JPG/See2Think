"""extract_index

读取一个或多个 JSON 文件（命令行参数提供），从每个文件中提取值为 true 的键，
按升序排序后写入到一个输出文件，每个索引占一行。

行为约定（合理假设）：
- 输入文件为 JSON 对象，键通常为数字的字符串（例如 "0", "1" ...），值为布尔值。
- 输出文件位于与输入文件相同目录，文件名为 <input_basename>.idx（例如 a.json -> a.idx）。
- 对于可解析为整数的键，按照数值升序排序；否则按字符串升序排序。

用法示例：
  python solve/extract_index.py a.json b.json
  python solve/extract_index.py --out-dir out_dir a.json

"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable, List, Tuple


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="从 JSON 文件中提取值为 true 的键并按升序输出每行一个索引"
    )
    p.add_argument("files", nargs="+", help="一个或多个要处理的 JSON 文件路径")
    p.add_argument(
        "--out-dir", help="可选：指定输出目录（保持输入文件名但扩展名为 .idx）"
    )
    p.add_argument("--ext", default=".idx", help="输出文件扩展名，默认 .idx")
    p.add_argument(
        "--print", action="store_true", help="在终端打印结果（同时仍写入文件）"
    )
    p.add_argument(
        "--output", help="合并输出文件路径（将所有输入文件的结果写入一个文件）"
    )
    return p.parse_args(list(argv) if argv is not None else None)


def read_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_true_keys(d: dict) -> List[str]:
    # 只保留值为真（严格等于 True 或 truthy）的键
    return [k for k, v in d.items() if v is True]


def sort_keys(keys: Iterable[str]) -> List[str]:
    # 尝试将键解析为整数以进行数值排序，否则回退到字符串排序
    parsed: List[Tuple[bool, int | str, str]] = []
    for k in keys:
        try:
            parsed.append((True, int(k), k))
        except Exception:
            parsed.append((False, k, k))
    # 先按是否为整数（整数优先），再按数值或字符串排序
    parsed.sort(key=lambda t: (not t[0], t[1]))
    return [orig for (_, _, orig) in parsed]


def write_output_file(output_path: str, keys: List[str]) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(f"{k}\n")
        print(f"已写入 {len(keys)} 个索引到 {output_path}")


def process_file(path: str) -> List[str]:
    """Process a single JSON file. Returns the sorted list of true keys."""
    try:
        data = read_json_file(path)
    except Exception as e:
        raise RuntimeError(f"无法读取或解析 JSON 文件 {path}: {e}")

    if not isinstance(data, dict):
        raise RuntimeError(f"文件 {path} 中 JSON 顶层不是对象(dict)")

    keys_true = extract_true_keys(data)
    return sort_keys(keys_true)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    all_keys = []
    any_failed = False

    for p in args.files:
        try:
            sorted_keys = process_file(p)
            all_keys.extend(sorted_keys)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            any_failed = True

    # 合并输出到一个文件
    if args.output:
        all_keys = sort_keys(all_keys)
        write_output_file(args.output, all_keys)
        if args.print:
            print(f"合并输出文件: {args.output} (count={len(all_keys)})")
            for k in all_keys:
                print(k)

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
