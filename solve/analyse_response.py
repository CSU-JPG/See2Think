"""
对模型回答进行分析
判断步骤是否与 golden 推理链中步骤对齐
给出不同的标签: Correct(1), Unverifiable(0.5), Incorrect(0)
steps得分与answer得分加权平均, 计算最终得分
"""
import argparse
import json
from openai import OpenAI
import os

def read_content_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
    
def save_content(text, path):
    try:
        with open(path, 'w') as f:
            f.write(text)
        print("* save to", path)
    except Exception as e:
        print("* error writing to", path)
        print(f"Error writing to {path}: {e}")

LLM_JUDGE_PROMPT = read_content_from_file("llm_judge_prompt.txt")

def judge(text:str, openai_client: OpenAI):
    print("* judging...")
    messages = [{"role": "system", 
                 "content": LLM_JUDGE_PROMPT}]
    messages.append({"role": "user", "content": text})
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=messages
    )
    return response.choices[0].message.content

def strip_json_comments(json_string: str) -> str:
    json_string = json_string.strip()
    if json_string.startswith("```json") and json_string.endswith("```"):
        json_string = json_string[7:-3].strip()
    return json_string

def create_message(question_text:str, golden_text: str, model_response_text: str) -> str:
    return f"""
[Question]
{question_text}
[Reference Answer]
{golden_text}
[Model Answer]
{model_response_text}
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze model response")
    parser.add_argument("--question", type=str, default="question.txt", help="Path to the question file")
    parser.add_argument("--golden", type=str, default="golden.txt", help="Path to the golden answer file")
    parser.add_argument("--model_response", type=str, default="model_response.txt", help="Path to the model response file")
    parser.add_argument("--output", type=str, default="analysis_result.json", help="Path to save the analysis result")
    args = parser.parse_args()
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", None)
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    question_text = read_content_from_file(args.question)
    golden_text = read_content_from_file(args.golden)
    model_response_text = read_content_from_file(args.model_response)
    message = create_message(question_text, golden_text, model_response_text)
    # print(judge(message, openai_client))
    save_content(strip_json_comments(judge(message, openai_client)), args.output)
    # print(message)
