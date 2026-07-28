import os
import json
import argparse
import glob
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
import time

# ================= 配置区域 =================
API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MODEL_NAME = os.getenv("EVAL_MODEL", "gpt-4o") 

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def llm_judge(question, gold_answer, model_answer):
    """
    使用大模型判断回答是否正确。
    """
    if not model_answer:
        return False

    prompt = f"""
You are a strict evaluator.
Please verify if the Model's Answer matches the Reference Answer based on the Question.

Question: {question}
Reference Answer: {gold_answer}
Model's Answer: {model_answer}

Instruction:
1. Ignore minor formatting differences (e.g., "2" vs "2.0", "x=2" vs "2").
2. For multiple choice or specific counts, ensure exact logical match.
3. If the model answer contains boxed latex like \\boxed{{2}}, extract the content to compare.

Return a JSON object with a single boolean key "correct".
Example: {{"correct": true}}
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("correct", False)
    except Exception as e:
        print(f"LLM Judge Error: {e}")
        return False

def process_single_file(file_path):
    """
    处理单个 JSON 文件，计算 ACC 和步骤统计
    """
    group_name = os.path.basename(file_path).replace(".json", "")
    print(f"Evaluating: {group_name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_tasks = len(data)
    if total_tasks == 0:
        return group_name, None

    # 1. 统计步骤信息
    total_steps = 0
    total_action_steps = 0 # 有图片的步骤
    
    # 2. 并发进行 ACC 判题
    correct_count = 0
    
    # 只需要判断是否包含 "optional" 关键字来决定是否统计动作占比
    # 但为了全面，我们可以对所有组都统计，后续只看需要的
    is_optional_group = "optional" in group_name

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交判题任务
        future_to_task = {
            executor.submit(llm_judge, t.get('question'), t.get('gold_answer'), t.get('model_final_answer')): t 
            for t in data
        }
        
        # 遍历任务统计步骤（不需要并发）
        for task in data:
            steps = task.get('steps', [])
            num_steps = len(steps)
            total_steps += num_steps
            
            for step in steps:
                # 判断该步骤是否有生成的图片/动作
                # 根据之前的 schema, step['image'] 不为 None 即为有动作
                if step.get('image'):
                    total_action_steps += 1

        # 获取判题结果
        for future in tqdm(concurrent.futures.as_completed(future_to_task), total=total_tasks, desc=f"Judging {group_name}"):
            is_correct = future.result()
            if is_correct:
                correct_count += 1

    # 3. 计算指标
    accuracy = (correct_count / total_tasks) * 100 if total_tasks > 0 else 0
    avg_steps = total_steps / total_tasks if total_tasks > 0 else 0
    
    # 动作率：(有动作的步骤 / 总步骤) * 100
    action_ratio = (total_action_steps / total_steps) * 100 if total_steps > 0 else 0

    result = {
        "group_name": group_name,
        "sample_count": total_tasks,
        "accuracy": round(accuracy, 2),
        "total_steps": total_steps,
        "avg_steps": round(avg_steps, 2),
        "action_steps_count": total_action_steps,
        "action_step_ratio": round(action_ratio, 2) # 百分比
    }
    
    return group_name, result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-files", nargs='+', required=True, help="List of json files to evaluate")
    parser.add_argument("--output-file", type=str, default="evaluation_report.json", help="Path to save the report")
    args = parser.parse_args()

    all_results = {}

    for file_path in args.input_files:
        if not os.path.exists(file_path):
            print(f"Warning: File not found {file_path}")
            continue
            
        group_name, metrics = process_single_file(file_path)
        if metrics:
            all_results[group_name] = metrics

    # 保存结果
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nEvaluation complete. Results saved to {args.output_file}")
    
    # 打印一个简单的摘要表格
    print(f"{'Group Name':<60} | {'Acc (%)':<10} | {'Avg Steps':<10} | {'Act Ratio(%)':<15}")
    print("-" * 105)
    for name, m in all_results.items():
        print(f"{name:<60} | {m['accuracy']:<10} | {m['avg_steps']:<10} | {m['action_step_ratio']:<15}")

if __name__ == "__main__":
    main()