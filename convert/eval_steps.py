import os
import json
import argparse
import base64
import random
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
import time

# ================= 配置区域 =================
API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MODEL_NAME = os.getenv("EVAL_MODEL", "gpt-4o") 

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def encode_image(image_path):
    """将图片转换为 Base64 字符串"""
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def vlm_step_judge(question, original_image_path, step_data):
    """
    使用 VLM 评估单个步骤的质量
    """
    step_text = step_data.get('content_text', '')
    step_image_info = step_data.get('image') # 这是一个字典 {relative_path, absolute_path}
    
    # 准备原图
    base64_original = encode_image(original_image_path)
    if not base64_original:
        return None # 无法评估

    system_prompt = """You are an expert Multimodal Reasoning Auditor. 
Your task is to evaluate a single step in a reasoning chain used to solve a visual problem.
Output a JSON object with the following boolean or integer fields:
1. "hallucination": (boolean) Does the text mention objects/attributes NOT present in the Original Image?
2. "alignment": (boolean) If a Step Image is provided, does it correctly visualize the text intent? (If no step image, return true).
3. "logic_score": (0-1) Is the text reasoning mathematically/logically sound?
4. "necessity_score": (1-5) Was generating this specific step image necessary/helpful? (1=Useless/Redundant, 5=Crucial). If no image, return 0.
5. "critique": (string) A concise explanation (1-2 sentences) justifying your scores. E.g., "The text correctly identifies the red cube, but the generated image highlights the blue sphere." or "Logical step is valid."
"""
    messages = [
        {
            "role": "system", 
            "content": system_prompt
        }
    ]

    user_content = [
        {"type": "text", "text": f"Question: {question}\n\n"}
    ]

    # 添加原图
    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_original}"}
    })
    
    user_content.append({"type": "text", "text": f"Current Step Text Analysis: \"{step_text}\"\n"})

    # 如果当前步骤生成了图片，也传给模型看
    if step_image_info and step_image_info.get('absolute_path'):
        step_img_path = step_image_info.get('absolute_path')
        base64_step = encode_image(step_img_path)
        if base64_step:
            user_content.append({"type": "text", "text": "Current Step Generated Action Image:"})
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_step}"}
            })
    else:
        user_content.append({"type": "text", "text": "Current Step: No image generated."})

    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=500
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"VLM Judge Error: {e}")
        return None

# Markdown 报告生成
def generate_markdown_report(group_name, cases, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Evaluation Report: {group_name}\n\n")

        categories = {
            "perfect": "Positive Examples (High Quality)",
            "hallucination": "Negative: Hallucinations",
            "alignment_fail": "Negative: Text-Image Misalignment",
            "logic_fail": "Negative: Logic Failures"
        }

        for cat_key, cat_title in categories.items():
            f.write(f"## {cat_title}\n\n")
            samples = cases.get(cat_key, [])
            if not samples:
                f.write("_No examples found._\n\n")
                continue

            for idx, sample in enumerate(samples[:5]): 
                # 直接从 sample 快照中读取，不回查 task['steps']
                f.write(f"### Example {idx+1} (ID: {sample['task_id']})\n")
                f.write(f"**Question**: {sample['question']}\n\n")
                f.write(f"**Gold Answer**: {sample['gold_answer']}\n\n")
                
                q_img = os.path.join(sample['base_path'], sample['question_image'])
                f.write(f"**Original Image**:\n\n![]({q_img})\n\n")
                
                # 从快照读取步骤信息
                step_info = sample['target_step']
                f.write(f"**Step {step_info.get('step_index', '?')}**:\n")
                f.write(f"> {step_info.get('content_text', '')}\n\n")
                
                if step_info.get('image'):
                    img_path = step_info['image']['absolute_path']
                    f.write(f"**Action Image**:\n\n![]({img_path})\n\n")
                
                # 提取并展示 Critique
                audit_res = sample['eval_result']
                critique_text = audit_res.get('critique', 'No critique provided.')

                # 分数展示
                score_summary = {k:v for k, v in audit_res.items() if k != "critique"}
                f.write(f"**Auditor Critique**:\n>{critique_text}\n\n")
                f.write(f"**Scores**:\n>{json.dumps(score_summary, indent=2)}\n\n")
                

def process_single_task_evaluation(task):
    """评估单个 Task 的所有步骤, 并返回是否值得作为案例"""
    question = task['question']
    base_path = task['base_path']
    q_image_name = task.get('question_image', 'p0.png')
    original_image_path = os.path.join(base_path, q_image_name)
    
    steps = task.get('steps', [])
    
    task_metrics = {
        "hallucination_count": 0,
        "alignment_fail_count": 0,
        "logic_fail_count": 0,
        "total_necessity_score": 0,
        "image_step_count": 0,
        "step_count": len(steps)
    }

    # 用于收集值得作为案例的步骤信息
    interesting_cases = {
        "perfect": [],
        "hallucination": [],
        "alignment_fail": [],
        "logic_fail": []
    }

    is_perfect_task = True

    # 串行评估每个步骤
    for i, step in enumerate(steps):
        res = vlm_step_judge(question, original_image_path, step)
        if res:
            if res.get('hallucination'): task_metrics['hallucination_count'] += 1
            if not res.get('alignment'): task_metrics['alignment_fail_count'] += 1
            if res.get('logic_score') == 0: task_metrics['logic_fail_count'] += 1
            
            nec = res.get('necessity_score', 0)
            if nec > 0:
                task_metrics['total_necessity_score'] += nec
                task_metrics['image_step_count'] += 1
            
            case_snapshot = {
                "task_id": task.get('id'),
                "question": question,
                "gold_answer": task.get('gold_answer'),
                "base_path": base_path,
                "question_image": q_image_name,
                "target_step": step, # 直接保存这一步的对象
                "eval_result": res
            }

            if res.get('hallucination'):
                interesting_cases['hallucination'].append(case_snapshot)
                is_perfect_task = False
            elif not res.get('alignment') and step.get('image'): # 只有当有图且不匹配时才算
                interesting_cases['alignment_fail'].append(case_snapshot)
                is_perfect_task = False
            elif res.get('logic_score') == 0:
                interesting_cases['logic_fail'].append(case_snapshot)
                is_perfect_task = False
            elif res.get('logic_score') == 1 and res.get('alignment', True) and not res.get('hallucination'):
                # 只有当这是关键步骤（有图且分高）时才记录为完美步骤案例
                if step.get('image') and res.get('necessity_score', 0) >= 4:
                    interesting_cases['perfect'].append(case_snapshot)
    
    return task_metrics, interesting_cases

def process_single_file(file_path, max_samples=None):
    group_name = os.path.basename(file_path).replace(".json", "")
    print(f"Deep Evaluating: {group_name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 采样逻辑：如果数据太多，为了省钱省时间，进行随机采样
    if max_samples and len(data) > max_samples:
        print(f"Sampling {max_samples} tasks from {len(data)} total.")
        data = random.sample(data, max_samples)
    
    aggregated_results = {
        "total_steps_eval": 0,
        "total_image_steps_eval": 0,
        "hallucination_rate": 0.0, # 步骤级幻觉率
        "alignment_acc": 0.0,      # 文图一致性准确率
        "logic_acc": 0.0,          # 逻辑正确率
        "avg_necessity": 0.0       # 图片生成的平均必要性 (1-5)
    }

    all_group_cases = {
        "perfect": [],
        "hallucination": [],
        "alignment_fail": [],
        "logic_fail": []
    }

    total_metrics = {
        "hallucination": 0,
        "alignment_fail": 0,
        "logic_fail": 0,
        "nec_sum": 0,
        "img_steps": 0,
        "total_steps": 0
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_single_task_evaluation, task) for task in data]
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(data)):
            try:
                metrics, cases = future.result()
                
                # 累加统计
                total_metrics["total_steps"] += metrics['step_count']
                total_metrics["img_steps"] += metrics['image_step_count']
                total_metrics["hallucination"] += metrics['hallucination_count']
                total_metrics["alignment_fail"] += metrics['alignment_fail_count']
                total_metrics["logic_fail"] += metrics['logic_fail_count']
                total_metrics["nec_sum"] += metrics['total_necessity_score']
                
                # 收集案例 (限制数量防止内存爆炸)
                for k in all_group_cases:
                    if len(all_group_cases[k]) < 5: # 每种类型只需要收集前5个
                        all_group_cases[k].extend(cases[k])
            except Exception as e:
                print(f"Task error: {e}")

    # 计算最终统计指标
    aggregated_results["total_steps_eval"] = total_metrics["total_steps"]
    aggregated_results["total_image_steps_eval"] = total_metrics["img_steps"]
    if total_metrics["total_steps"] > 0:
        aggregated_results["hallucination_rate"] = round((total_metrics["hallucination"] / total_metrics["total_steps"]) * 100, 2)
        aggregated_results["logic_acc"] = round(((total_metrics["total_steps"] - total_metrics["logic_fail"]) / total_metrics["total_steps"]) * 100, 2)
        aggregated_results["alignment_acc"] = round(((total_metrics["total_steps"] - total_metrics["alignment_fail"]) / total_metrics["total_steps"]) * 100, 2)
    if total_metrics["img_steps"] > 0:
        aggregated_results["avg_necessity"] = round(total_metrics["nec_sum"] / total_metrics["img_steps"], 2)

    # 生成报告
    case_json_filename = file_path.replace(".json", "_cases_detail.json")
    try:
        with open(case_json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_group_cases, f, indent=2, ensure_ascii=False)
        print(f"Detailed Cases JSON saved to: {case_json_filename}")
    except Exception as e:
        print(f"Error saving detail json: {e}")

    # 生成 Markdown 报告
    report_filename = file_path.replace(".json", "_case_study.md")
    try:
        generate_markdown_report(group_name, all_group_cases, report_filename)
        print(f"Markdown Report saved to: {report_filename}")
    except Exception as e:
        print(f"Error saving markdown: {e}")

    return group_name, aggregated_results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-files", nargs='+', required=True, help="List of json files")
    parser.add_argument("--output-file", type=str, default="deep_eval_report.json")
    parser.add_argument("--max-samples", type=int, default=50, help="Max tasks to evaluate per file to save cost")
    args = parser.parse_args()

    all_results = {}

    for file_path in args.input_files:
        if not os.path.exists(file_path): continue
        try:
            group_name, metrics = process_single_file(file_path, args.max_samples)
            all_results[group_name] = metrics
        except Exception as e:
            print(f"Critical error processing file {file_path}: {e}")

    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n" + "="*80)
    print(f"{'Group Name':<50} | {'Halluc(%)':<10} | {'Align(%)':<10} | {'Logic(%)':<10} | {'Nec(1-5)':<10}")
    print("-" * 100)
    for name, m in all_results.items():
        print(f"{name:<50} | {m['hallucination_rate']:<10} | {m['alignment_acc']:<10} | {m['logic_acc']:<10} | {m['avg_necessity']:<10}")

if __name__ == "__main__":
    main()
