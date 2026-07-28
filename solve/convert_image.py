import os
import cv2
import json
from pathlib import Path


def convert_to_edge(image_path: str, output_path: str):
    """
    convert image to edge map using canny algorithm
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        edges = cv2.Canny(gray, 50, 150)
        cv2.imwrite(output_path, edges)
        print(f"Edge map saved to {output_path}")
        return edges
    else:
        print("No output path provided, edge map not saved.")
        return None


def convert_to_depth(image_path: str, output_path: str):
    """
    convert image to depth map using simple thresholding
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Simple depth estimation using thresholding (placeholder for actual depth estimation model)
    _, depth_map = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, depth_map)
        print(f"Depth map saved to {output_path}")
    else:
        print("No output path provided, depth map not saved.")
    return depth_map


def process_image(
    image_path: str, edge_output_path: str = None, depth_output_path: str = None
):
    """
    Process the image to generate edge and depth maps.
    """
    edge_map = convert_to_edge(image_path, edge_output_path)
    depth_map = convert_to_depth(image_path, depth_output_path)
    return edge_map, depth_map


def process_all_images(json_path: str):
    """
    process all images in the json file (json_path)
    the json file contains an array of objects with "image_path" field
    one example object:
    {
        "image_path": "annotation/dataset/data/clevr_math/val/images/CLEVR_val_000000.png",
        ...
    }
    the edge maps and depth maps will be saved in
        `annotation/dataset/data/clevr_math/val/images/edge_maps/`
        and
        `annotation/dataset/data/clevr_math/val/images/depth_maps/`
        respectively
    """

    with open(json_path, "r") as f:
        data = json.load(f)

    for index, element in enumerate(data):
        image_path = element["image_path"]
        edge_output_path = (
            Path(image_path).parent / "edge_maps" / element["image_path"].split("/")[-1]
        )
        depth_output_path = (
            Path(image_path).parent
            / "depth_maps"
            / element["image_path"].split("/")[-1]
        )
        os.makedirs(edge_output_path.parent, exist_ok=True)
        os.makedirs(depth_output_path.parent, exist_ok=True)
        process_image(
            image_path=str(image_path),
            edge_output_path=str(edge_output_path),
            depth_output_path=str(depth_output_path),
        )
        # for every 100 images, print progress
        if index % 100 == 0:
            print(f"Processed {index} / {len(data)} images")


if __name__ == "__main__":
    # json_path = "selected_1200.json"
    json_path = "json/annotation_dataset_data_m3cot_test1_data.json"
    process_all_images(json_path)
