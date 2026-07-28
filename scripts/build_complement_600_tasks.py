"""Create the 600 IDs not present in an existing 600-row answer evaluation."""

import argparse
import json
from pathlib import Path


def task_key(row: dict) -> str:
    return row["relative_source_dir"].replace("\\", "/") + "::" + str(row["sample_id"])


def canonical_key(row: dict) -> str:
    path = row["path"].replace("\\", "/")
    prefix = "annotation/dataset/data/"
    if path.startswith(prefix):
        path = path[len(prefix):]
    if path.endswith("/data.json"):
        path = path[: -len("/data.json")]
    return path + "::" + str(row["id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluated-jsonl", required=True)
    parser.add_argument("--all-tasks", default="json/tasks_see2thinkbench_1200task_available.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    evaluated = {
        task_key(json.loads(line))
        for line in Path(args.evaluated_jsonl).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    all_rows = json.loads(Path(args.all_tasks).read_text(encoding="utf-8"))
    complement = [row for row in all_rows if canonical_key(row) not in evaluated]
    if len(evaluated) != 600 or len(complement) != 600:
        raise RuntimeError(f"Expected a 600/600 split, got evaluated={len(evaluated)}, complement={len(complement)}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(complement, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for row in complement:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    print(f"wrote {len(complement)} rows to {args.output}; categories={counts}")


if __name__ == "__main__":
    main()
