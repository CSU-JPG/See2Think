import json
import os

# json_files = [
#     "json/annotation_dataset_data_clevr_math_val_data.json",
#     "json/annotation_dataset_data_emma_chemistry_data.json",
#     "json/annotation_dataset_data_emma_math_data.json",
#     "json/annotation_dataset_data_emma_physics_data.json",
#     "json/annotation_dataset_data_m3cot_test0_data.json",
#     "json/annotation_dataset_data_m3cot_test1_data.json",
#     "json/annotation_dataset_data_math_data.json",
#     "json/annotation_dataset_data_prism_black_white_blocks_data.json",
#     "json/annotation_dataset_data_prism_position_style_attribute_count_data.json",
#     "json/annotation_dataset_data_prism_shape_reasoning_others_data.json",
#     "json/annotation_dataset_data_prism_spatial_reasoning_data.json",
#     "json/annotation_dataset_data_prism_special_patterns_data.json",
#     "json/annotation_dataset_data_prism_text_letter_number_data.json",
# ]

json_files = [
    "json/annotation_dataset_data_m3cot_test1_data.json",
]


def create_tasks():
    """
    convert
        {
            "question": "xxx",
            "image_path": "xxx",
            "source_dataset": "xxx",
            "source_index": 8
        }
    to
        {
            "order": 0, # enum index
            "path": "xxx", # source_dataset
            "id": 0 # source_index
        },
    """
    for json_file in json_files:
        with open(json_file, "r") as f:
            data = json.load(f)

        tasks = []
        for idx, item in enumerate(data):
            task = {
                "order": idx,
                "path": item["source_dataset"],
                "id": item["source_index"],
            }
            tasks.append(task)

        output_file = f"json/tasks_{os.path.basename(json_file)}"
        with open(output_file, "w") as f:
            json.dump(tasks, f, indent=4)
        print(f"Created {output_file} with {len(tasks)} tasks.")


if __name__ == "__main__":
    create_tasks()
