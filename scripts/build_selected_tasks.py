"""Write a small task subset by canonical task key."""

import argparse
import json
from pathlib import Path


def key(row: dict) -> str:
    path = row["path"].replace("\\", "/")
    prefix = "annotation/dataset/data/"
    if path.startswith(prefix):
        path = path[len(prefix):]
    if path.endswith("/data.json"):
        path = path[: -len("/data.json")]
    return f"{path}::{row['id']}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--keys", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    wanted = set(args.keys)
    rows = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    selected = [row for row in rows if key(row) in wanted]
    if len(selected) != len(wanted):
        raise RuntimeError(f"Requested {len(wanted)} keys, found {len(selected)}")
    Path(args.output).write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(selected)} rows to {args.output}")


if __name__ == "__main__":
    main()
