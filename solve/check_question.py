"""
将图片转为文字描述, 文字描述和问题拼接后给大模型进行问答
用于检查问题是否符合要求
如果模型在5次回答中有3次以上回答正确, 则判定该问题不符合要求（即不需要图片, 仅靠文字描述就可以解决）
"""

import argparse
import os
import sys
from openai import OpenAI
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from auto_solve import (
    create_question,
    get_json_array_element,
    image_to_base64,
    get_json_array_element
)

MAX_ATTEMPTS = 5
SUCCESS_THRESHOLD = 3

# new constants for image call retries
IMAGE_CALL_MAX_RETRIES = 3
IMAGE_CALL_BACKOFF_BASE = 1.0  # seconds

def parse_range(s:str):
    try:
        x,y = map(int, s.split(","))
        return x, y
    except ValueError:
        raise argparse.ArgumentTypeError("range必须是'x,y'格式")

def chat(openai_client: OpenAI, model:str, prompt: str, image:str="") -> str:
    if image is None or image == "":
        return chat_with_images(openai_client, model, prompt, [])
    return chat_with_images(openai_client, model, prompt, [image])

def chat_with_images(openai_client: OpenAI, model:str, prompt: str, images:list[str]) -> str:
    """Call the model with optional images. Retries on exceptions with exponential backoff."""
    content = []
    content.append({"type": "text", "text": prompt})
    for image in images:
        content.append({"type": "image_url", "image_url": f"data:image/png;base64,{image}"})

    last_exc = None
    for attempt in range(1, IMAGE_CALL_MAX_RETRIES + 1):
        try:
            response = openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    },
                ]
            )
            # successful call
            return response.choices[0].message.content
        except Exception as e:
            last_exc = e
            wait = IMAGE_CALL_BACKOFF_BASE * (2 ** (attempt))
            print(f"chat_with_images attempt {attempt} failed: {e}. Retrying in {wait:.2f}s...")
            time.sleep(wait)

    # all retries exhausted
    print(f"chat_with_images: all {IMAGE_CALL_MAX_RETRIES} attempts failed. Last error: {last_exc}")
    return ""

def image_to_text_description(openai_client: OpenAI, model:str, image_base64: str) -> str:
    prompt = """
    You will be provided with an image in base64 format. Your task is to analyze the image and generate a detailed textual description of its content.
    Focus on capturing important elements, objects, and context present in the image. The description should be clear and informative, enabling someone who cannot see the image to understand what it depicts.
    Provide the description in a concise paragraph.
    """
    return chat(openai_client=openai_client, model=model, prompt=prompt,image=image_base64)


def judge_answer_correctness(openai_client: OpenAI, model:str, answer: str, response: str) -> bool:
    prompt = f"""
You will be given a solution process and a correct answer. Your task is to verify if the final result derived from the solution process matches the correct answer.
[Solution Process]
{response}
[Correct Answer]
{answer}
Does the final result from the [Solution Process] match the [Correct Answer]? Respond with only "yes" or "no".
"""
    verification_response = chat(openai_client, model, prompt)
    return "yes" in verification_response.lower()

def check(args, openai_client, description:str, index:int):
    """
    返回True表示是图像强依赖的
    返回False表示不是图像强依赖的
    """
    print(f"{args.dataset}_{index}: Checking question validity")
    prefix = "annotation/dataset/data/" + args.dataset + "/"
    element = get_json_array_element(prefix + "data.json", index)
    answer = element.get("answer", "")
    question = create_question(element, with_answer=False)
    combined_prompt = f"Image Description: {description}\nQuestion: {question}"

    success_count = 0
    fail_count = 0
    for _ in range(MAX_ATTEMPTS):
        response = chat(openai_client, model=args.model, prompt=combined_prompt)
        if judge_answer_correctness(openai_client, model=args.model, answer=answer, response=response):
            success_count += 1
        else:
            fail_count += 1
        if fail_count > (MAX_ATTEMPTS - SUCCESS_THRESHOLD):
            break
        if success_count >= SUCCESS_THRESHOLD:
            print(f"Question at index {index} is deemed solvable without the image.")
            return False
    print(f"Question at index {index} requires the image for solving.")
    print(f"acc: {success_count} / {MAX_ATTEMPTS}")
    return True

def check_range(args, openai_client):
    """
    多线程版本的 check_range 函数，可以正确处理 Ctrl+C
    """
    prefix = "annotation/dataset/data/" + args.dataset + "/"
    indices = range(args.range[0], args.range[1])

    # Thread worker for a single index
    def worker(index: int):
        print(f"Checking index: {index}")
        element = get_json_array_element(prefix + "data.json", index)
        description = image_to_text_description(
            openai_client,
            model=args.model,
            image_base64=image_to_base64(
                prefix + element.get("image_path", "")
            )
        )
        valid = check(args, openai_client, description, index)
        return index, valid

    # Use ThreadPoolExecutor for concurrency
    max_workers = getattr(args, "workers", None) or min(8, max(1, max(1, len(indices))))
    results = {}

    # 1. 手动创建 executor，不要使用 'with' 语句
    executor = ThreadPoolExecutor(max_workers=max_workers)
    
    try:
        # 2. 正常提交任务
        future_to_index = {executor.submit(worker, idx): idx for idx in indices}
        
        # 3. 正常获取结果
        for fut in as_completed(future_to_index):
            idx = future_to_index[fut]
            try:
                index, valid = fut.result()
                results[index] = valid
            except Exception as e:
                # 注意：这个 except Exception 不会捕获 KeyboardInterrupt，这是正确的！
                print(f"Error processing index {idx}: {e}")
                results[idx] = False
                
    except KeyboardInterrupt:
        print(f"\n[!] 收到 Ctrl+C。正在强制关闭工作线程...")
        
        # 4. 在捕获到中断时，调用 shutdown(wait=False)
        #    告诉主线程不要等待工作线程
        
        # 如果你使用 Python 3.9+，可以使用 cancel_futures=True
        if sys.version_info >= (3, 9):
            executor.shutdown(wait=False, cancel_futures=True)
        else:
            # 对于 Python 3.8 及更早版本
            executor.shutdown(wait=False)
            
        print("[!] 线程池已关闭。正在退出。")
        # 主线程会在这里退出，由于工作线程是守护线程，它们将被强制终止
        
    else:
        # 5. (可选) 如果循环正常完成（没有按 Ctrl+C）
        print("所有任务完成。正常关闭线程池。")
        executor.shutdown(wait=True) # 正常等待
        
    return results

def check_indices(args, openai_client):
    indices = []
    if args.indices:
        with open(args.indices, "r") as f:
            indices = [int(line.strip()) for line in f.readlines()]
    results = {}
    prefix = "annotation/dataset/data/" + args.dataset + "/"

    # Thread worker for a single index
    def worker(index: int):
        print(f"Checking index: {index}")
        element = get_json_array_element(prefix + "data.json", index)
        description = image_to_text_description(
            openai_client,
            model=args.model,
            image_base64=image_to_base64(
                prefix + element.get("image_path", "")
            )
        )
        valid = check(args, openai_client, description, index)
        return index, valid

    # Use ThreadPoolExecutor for concurrency
    max_workers = getattr(args, "workers", None) or min(8, max(1, len(indices)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(worker, idx): idx for idx in indices}
        for fut in as_completed(future_to_index):
            idx = future_to_index[fut]
            try:
                index, valid = fut.result()
                results[index] = valid
            except Exception as e:
                print(f"Error processing index {idx}: {e}")
                results[idx] = False
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check questions in a dataset")
    parser.add_argument("--dataset", type=str, required=True, help="Path to the dataset")
    parser.add_argument("--model", type=str, default="gpt-5")
    parser.add_argument("--indices", type=str, help="line-separated list of indices to check, stored in a file")
    parser.add_argument("--workers", type=int, help="Number of concurrent workers", default=8)
    parser.add_argument("--range", type=parse_range, help="范围，格式为 x,y")
    parser.add_argument("--output", type=str, help="Output JSON file to save results", default="check_results.json")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    openai_base_url = os.environ.get("OPENAI_BASE_URL")
    if not openai_api_key or not openai_base_url:
        exit("Please set OPENAI_API_KEY and OPENAI_BASE_URL environment variables.")
    openai_client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
    args = parser.parse_args()
    # 把args转为json格式打印在控制台
    print("Arguments:", json.dumps(vars(args), indent=2))
    result = check_range(args, openai_client)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)