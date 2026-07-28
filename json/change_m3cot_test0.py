from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    data_path = (
        Path(__file__).resolve().parent
        / "tasks_annotation_dataset_data_m3cot_test0_data.json"
    )

    with data_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise TypeError("期望读取到数组数据")

    for i, item in enumerate(data):
        if isinstance(item, dict):
            item["id"] = item.get("order", i)

    data = data[:72]

    with data_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
