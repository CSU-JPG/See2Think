import csv
import json
from pathlib import Path

tasks_path = Path("json/tasks_see2thinkbench_1200task_available.json")
missing_path = Path(
    "final_results_1200/full/"
    "qwen3-vl-32b-instruct/_missing.csv"
)
output_path = Path(
    "newtasks/qwen3vl32b_instruct_vaot_full_missing_render_28.json"
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

with missing_path.open(
    "r", encoding="utf-8-sig", newline=""
) as file:
    missing_rows = list(csv.DictReader(file))

missing_keys = {
    (
        row["relative_source_dir"].replace("\\", "/"),
        int(row["sample_id"]),
    )
    for row in missing_rows
}

selected = [
    task
    for task in tasks
    if (
        rel_source_dir(task["path"]),
        int(task["id"]),
    ) in missing_keys
]

if len(selected) != len(missing_keys):
    found = {
        (
            rel_source_dir(task["path"]),
            int(task["id"]),
        )
        for task in selected
    }
    unresolved = sorted(missing_keys - found)
    raise RuntimeError(
        f"Missing CSV has {len(missing_keys)} keys, "
        f"but only matched {len(selected)} tasks. "
        f"Unresolved={unresolved}"
    )

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps(selected, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Wrote {len(selected)} tasks to {output_path}")
