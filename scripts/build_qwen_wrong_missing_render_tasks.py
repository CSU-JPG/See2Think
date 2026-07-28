import csv
import json
from pathlib import Path

tasks_path = Path("json/tasks_see2thinkbench_1200task_available.json")
manifest_path = Path(
    "final_results_1200/wrong_render/"
    "qwen3-vl-32b-instruct/_manifest.csv"
)
output_path = Path(
    "newtasks/qwen3vl32b_instruct_vaot_wrong_render_missing_render_28.json"
)

DATA_PREFIX = "annotation/dataset/data/"

def rel_source_dir(data_path: str) -> str:
    path = data_path.replace("\\", "/")
    if path.startswith(DATA_PREFIX):
        path = path[len(DATA_PREFIX):]
    if path.endswith("/data.json"):
        path = path[:-len("/data.json")]
    return path

tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
rows = list(csv.DictReader(manifest_path.open("r", encoding="utf-8-sig", newline="")))

missing_keys = {
    (row["relative_source_dir"].replace("\\", "/"), int(row["sample_id"]))
    for row in rows
    if row["status"] == "missing_render"
}

selected = [
    task for task in tasks
    if (rel_source_dir(task["path"]), int(task["id"])) in missing_keys
]

if len(selected) != len(missing_keys):
    found = {
        (rel_source_dir(task["path"]), int(task["id"]))
        for task in selected
    }
    unresolved = sorted(missing_keys - found)
    raise RuntimeError(
        f"Need {len(missing_keys)} tasks, matched {len(selected)}. "
        f"Unresolved={unresolved}"
    )

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps(selected, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Wrote {len(selected)} tasks to {output_path}")
