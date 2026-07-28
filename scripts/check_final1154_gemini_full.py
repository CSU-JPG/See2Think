import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tasks = json.load(open(root / "json/tasks_see2thinkbench_1154task_available.json", encoding="utf-8"))
out = root / "newtasks/final1154_gemini-3.5-flash_vaot_full_floor"

completed = []
missing = []
for pos, task in enumerate(tasks):
    path = Path(task["path"])
    idx = int(task.get("id", task.get("index")))
    if not path.is_absolute():
        path = root / path
    rel = path.parent.relative_to(root / "annotation/dataset/data")
    d = out / rel / "banana_gemini-3.5-flash_vaot_full" / str(idx)
    steps = d / "steps.md"
    has_render = any(
        p.name.startswith("p")
        and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
        and p.name != "p0.png"
        and p.stat().st_size > 0
        for p in d.glob("p*")
    ) if d.exists() else False
    ok = steps.exists() and steps.stat().st_size > 0 and has_render
    if ok:
        completed.append(pos)
    else:
        missing.append((pos, str(rel).replace("\\", "/"), idx, steps.exists(), has_render))

completed_set = set(completed)
prefix = 0
for i in range(len(tasks)):
    if i in completed_set:
        prefix = i + 1
    else:
        break

print(f"valid_completed={len(completed)}")
print(f"contiguous_prefix_next_start={prefix}")
print("completed_by_source:")
c = Counter()
for pos in completed:
    path = Path(tasks[pos]["path"])
    if not path.is_absolute():
        path = root / path
    c[str(path.parent.relative_to(root / "annotation/dataset/data")).replace("\\", "/")] += 1
for key, value in sorted(c.items()):
    print(f"  {key}: {value}")
print("first_missing:")
for row in missing[:30]:
    print("  pos={0} source={1} id={2} steps={3} render={4}".format(*row))
