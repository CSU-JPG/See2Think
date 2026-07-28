import json
import os

with open("selected_241.json", "r", encoding="utf-8") as f:
    data = json.load(f)

classified_data = {}

for item in data:
    source_dataset = item["source_dataset"]
    if source_dataset not in classified_data:
        classified_data[source_dataset] = []
    classified_data[source_dataset].append(item)

for dataset, items in classified_data.items():
    print(f"Dataset: {dataset}")
    print(f"Number of items: {len(items)}")
    os.makedirs("json", exist_ok=True)
    with open(f'json/{dataset.replace("/", "_")}', "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=4)
    print("---")
