# pipeline.py
import os
import json
import glob
import argparse
from tqdm import tqdm
from parsers import MarkdownParser
from data_schema import TaskData

# === 配置路径 - 默认值 ===
DEFAULT_ROOT_DIR = "/media/lauv/WD/see2think/tasks/out/math/code_gemini-2.5-pro/"
DEFAULT_OUTPUT_FILE = "math_code_gemini-2.5-pro_output.json"

def process_single_task(folder_path):
    parser = MarkdownParser()
    folder_name = os.path.basename(folder_path) # e.g., "0"
    
    q_path = os.path.join(folder_path, "q.md")
    steps_path = os.path.join(folder_path, "steps.md")
    
    # 1. 解析 Q.md
    q_data = parser.parse_q_md(q_path)
    
    # 2. 解析 Steps.md
    steps_data = parser.parse_steps_md(steps_path, base_dir=folder_path)
    
    # 3. 组装数据
    task = TaskData(
        id=folder_name,
        base_path=folder_path,
        question=q_data["question"],
        gold_answer=q_data["answer"],
        steps=steps_data["steps"],
        model_final_answer=steps_data["final_answer"],
        parse_success=steps_data["success"],
        error_msg=steps_data["error"]
    )
    
    return task.to_dict()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Process task data from markdown files")
    parser.add_argument("--root-dir", type=str, default=DEFAULT_ROOT_DIR,
                        help=f"Root directory of task data (default: {DEFAULT_ROOT_DIR})")
    parser.add_argument("--output-file", type=str, default=DEFAULT_OUTPUT_FILE,
                        help=f"Output JSON file path (default: {DEFAULT_OUTPUT_FILE})")
    args = parser.parse_args()
    
    ROOT_DIR = args.root_dir
    OUTPUT_FILE = args.output_file
    
    # 获取所有子文件夹
    # 假设每个数字文件夹就是一个样本
    task_folders = [f for f in glob.glob(os.path.join(ROOT_DIR, "*")) if os.path.isdir(f)]
    task_folders.sort(key=lambda x: int(os.path.basename(x)) if os.path.basename(x).isdigit() else 0)
    
    results = []
    
    print(f"Found {len(task_folders)} tasks. Starting processing...")
    
    for folder in tqdm(task_folders):
        try:
            data = process_single_task(folder)
            results.append(data)
        except Exception as e:
            print(f"Critical error processing {folder}: {e}")
            # 记录失败的记录
            results.append({
                "id": os.path.basename(folder), 
                "parse_success": False, 
                "error_msg": f"Pipeline Crash: {str(e)}"
            })

    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"Done. Saved to {OUTPUT_FILE}")
    
    # 简单的统计
    failed_count = sum(1 for r in results if not r.get('parse_success', True))
    print(f"Total: {len(results)}, Failed: {failed_count}")

if __name__ == "__main__":
    main()