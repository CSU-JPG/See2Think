import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--subdir", required=True)
    parser.add_argument("--require-render", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    tasks = json.load(open(args.tasks, encoding="utf-8"))
    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = root / output_root

    for pos, task in enumerate(tasks):
        path = Path(task["path"])
        idx = int(task.get("id", task.get("index")))
        if not path.is_absolute():
            path = root / path
        rel = path.parent.relative_to(root / "annotation/dataset/data")
        d = output_root / rel / args.subdir / str(idx)
        steps = d / "steps.md"
        ok = steps.exists() and steps.stat().st_size > 0
        if ok and args.require_render:
            ok = any(
                p.name.startswith("p")
                and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
                and p.name != "p0.png"
                and p.stat().st_size > 0
                for p in d.glob("p*")
            )
        if not ok:
            print(pos)
            return
    print(len(tasks))


if __name__ == "__main__":
    main()
