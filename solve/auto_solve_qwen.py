import base64
import logging
import random
from PIL import Image
import time
import os
import re
import json
from pathlib import Path
import argparse
import shutil
from google import genai
from PIL import Image
from google.genai import types
from io import BytesIO
import base64, hashlib, io
import time
from openai import OpenAI
import subprocess
import sys
import traceback
import contextlib
from io import BytesIO, StringIO
from typing import List, Dict
import requests

try:
    from . import convert_image
except ImportError:
    import convert_image
import mimetypes

try:
    from . import constant
except ImportError:
    import constant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)

openai_client = None
banana_client = None
qwen_image_edit_client = None


# Environment controls for selecting which LLM endpoint to talk to.
LLM_BACKEND_ENV = "SEE2THINK_LLM_BACKEND"
DEFAULT_LLM_BACKEND = "openai"

# Qwen Image Edit service configuration (supports both online and local deployment)
QWEN_IMAGE_EDIT_BASE_URL_ENV = "QWEN_IMAGE_EDIT_BASE_URL"
QWEN_IMAGE_EDIT_API_KEY_ENV = "QWEN_IMAGE_EDIT_API_KEY"
QWEN_IMAGE_EDIT_MODEL_ENV = "QWEN_IMAGE_EDIT_MODEL"
DEFAULT_QWEN_IMAGE_EDIT_MODEL = "qwen-image-edit-2509"  # For online service


SLEEP_TIME = 2  # 每次请求后等待时间，单位秒
MAX_IMAGE_RETRY = 5  # 生成图片最大重试次数

def read_prompt_template(prompt_file: str):
    with open(prompt_file, "r", encoding="utf-8") as f:
        template = f.read()
    return template


def _normalize_llm_backend(raw_backend: str | None) -> str:
    """Map different backend aliases to a canonical name."""
    if not raw_backend:
        return DEFAULT_LLM_BACKEND
    normalized = raw_backend.strip().lower()
    if normalized in {"openai", "online", "cloud", "remote"}:
        return "openai"
    if normalized in {"local", "vllm", "qwen", "qwen_vl", "qwen-vl"}:
        return "vllm"
    raise ValueError(f"Unsupported LLM backend: {raw_backend}")


def _require_env(var_name: str, context: str) -> str:
    value = os.environ.get(var_name, "").strip()
    if not value:
        raise RuntimeError(
            f"{context} requires environment variable {var_name} to be set"
        )
    return value


def _create_chat_client_from_env():
    """Create the chat client (OpenAI-compatible) based on env vars."""
    backend = _normalize_llm_backend(os.environ.get(LLM_BACKEND_ENV))
    if backend == "openai":
        api_key = _require_env("OPENAI_API_KEY", "OpenAI backend")
        base_url = _require_env("OPENAI_BASE_URL", "OpenAI backend")
        return (
            OpenAI(api_key=api_key, base_url=base_url),
            {
                "backend": backend,
                "base_url": base_url,
                "api_key_source": "OPENAI_API_KEY",
            },
        )
    if backend == "vllm":
        base_url = _require_env("VLLM_BASE_URL", "vLLM (Qwen-VL) backend")
        api_key = (
            os.environ.get("VLLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or "EMPTY"
        )
        api_key_source = (
            "VLLM_API_KEY" if os.environ.get("VLLM_API_KEY") else "placeholder"
        )
        return (
            OpenAI(api_key=api_key, base_url=base_url),
            {
                "backend": backend,
                "base_url": base_url,
                "api_key_source": api_key_source,
            },
        )
    raise RuntimeError(f"LLM backend {backend} is not configured correctly")


def _create_qwen_image_edit_client_from_env():
    """
    Configure the Qwen Image Edit API client (online or local deployment).
    
    For online service, set:
      - QWEN_IMAGE_EDIT_BASE_URL: e.g., https://dashscope.aliyuncs.com/compatible-mode/v1
      - QWEN_IMAGE_EDIT_API_KEY: Your Alibaba Cloud API key
      - QWEN_IMAGE_EDIT_MODEL: e.g., qwen-vl-max-latest (optional)
    
    For local deployment, set:
      - QWEN_IMAGE_EDIT_BASE_URL: e.g., http://localhost:8000/v1
      - QWEN_IMAGE_EDIT_API_KEY: Local API key or "EMPTY"
      - QWEN_IMAGE_EDIT_MODEL: e.g., Qwen-Image-Edit-2509 (optional)
    
    Returns (client, meta_dict) or (None, None) when not configured.
    """
    base_url = os.environ.get(QWEN_IMAGE_EDIT_BASE_URL_ENV, "").strip()
    if not base_url:
        return None, None

    api_key = os.environ.get(QWEN_IMAGE_EDIT_API_KEY_ENV, "")
    if not api_key:
        logging.warning(
            f"{QWEN_IMAGE_EDIT_API_KEY_ENV} not set, using 'EMPTY' as placeholder"
        )
        api_key = "EMPTY"
    
    client = OpenAI(base_url=base_url, api_key=api_key)
    meta = {
        "base_url": base_url,
        "api_key_source": QWEN_IMAGE_EDIT_API_KEY_ENV,
        "api_key_set": bool(os.environ.get(QWEN_IMAGE_EDIT_API_KEY_ENV)),
    }
    return client, meta


def _request_qwen_image_edit(
    prompt: str,
    image_paths: list[str],
    output_path: str,
    log_prefix: str = "qwen image edit",
) -> str | None:
    """Send a prompt + reference images to the Qwen image edit API (online or local)."""
    if qwen_image_edit_client is None:
        logging.warning("%s client not configured, skipping", log_prefix)
        return None

    contents = [{"type": "text", "text": prompt}]
    for path in image_paths:
        try:
            image_data = encode_file_to_data_uri(path)
        except Exception as e:
            logging.warning("%s: failed to encode image '%s' (%s)", log_prefix, path, e)
            return None
        contents.append({"type": "image_url", "image_url": {"url": image_data}})

    model_name = os.environ.get(
        QWEN_IMAGE_EDIT_MODEL_ENV, DEFAULT_QWEN_IMAGE_EDIT_MODEL
    )

    max_attempts = 5
    delta = random.uniform(-0.5, 0.5) * SLEEP_TIME
    delay = SLEEP_TIME + delta
    time.sleep(delay)

    for attempt in range(1, max_attempts + 1):
        try:
            response = qwen_image_edit_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": contents}],
            )

            result = response.choices[0].message.content
            image_b64 = None

            if isinstance(result, str):
                image_b64 = result.strip()
            elif isinstance(result, list):
                for part in result:
                    if part.get("type") == "text":
                        logging.info(part.get("text", "").strip())
                        continue
                    if part.get("type") != "image_url":
                        continue
                    url = part.get("image_url", {}).get("url")
                    if not url:
                        continue
                    if url.startswith("data:"):
                        _, image_b64 = _parse_data_uri(url)
                    else:
                        image_b64 = url
                    break

            if not image_b64:
                logging.warning(
                    "%s attempt %d: response lacked image data, retrying",
                    log_prefix,
                    attempt,
                )
            else:
                try:
                    raw = base64.b64decode(image_b64)
                except Exception as decode_err:
                    logging.warning(
                        "%s attempt %d: failed to decode returned image: %s",
                        log_prefix,
                        attempt,
                        decode_err,
                    )
                else:
                    with open(output_path, "wb") as f:
                        f.write(raw)
                    logging.info(f"\n SAVE IMAGE: {output_path} \n")
                    return output_path

        except Exception as e:
            logging.warning(
                "%s attempt %d failed: %s: %s",
                log_prefix,
                attempt,
                type(e).__name__,
                e,
            )

        sleep_time = delay * (2 ** (attempt - 1))
        logging.warning("Retrying %s request in %.1fs ...", log_prefix, sleep_time)
        time.sleep(sleep_time)

    logging.warning("!!! Max attempts reached for %s, giving up !!!", log_prefix)
    return None


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


BASE_PROMPT_CODE = read_prompt_template("prompt/base_prompt_code.txt")
BASE_PROMPT_ACTION_JSON = read_prompt_template("prompt/base_prompt_action_json.txt")
BASE_PROMPT_OPTIONAL_CODE = read_prompt_template("prompt/base_prompt_optional_code.txt")
BASE_PROMPT_OPTIONAL_ACTION_JSON = read_prompt_template(
    "prompt/base_prompt_optional_action_json.txt"
)
GENERATE_IMAGE_PROMPT = read_prompt_template("prompt/generate_image_prompt.txt")
INTERFERENCE_PROMPT = read_prompt_template("prompt/interference_prompt.txt")
IMAGE_INTERFERENCE_PROMPT = read_prompt_template("prompt/image_interference_prompt.txt")
BASE_PROMPT_TEXT_ONLY = read_prompt_template("prompt/base_prompt_text_only.txt")


def _b64_bytes_len(b64: str) -> str:
    try:
        return len(base64.b64decode(b64, validate=True))
    except Exception:
        pad = b64.count("=")
        return (len(b64) // 4) * 3 - pad


def _parse_data_uri(uri: str):
    assert uri.startswith("data:")
    head, b64 = uri.split(",", 1)
    mime = head.split(";")[0][5:]
    return mime, b64


def preview_message(
    message_content: List[Dict],
    text_preview: int = 160,
    show_sha: bool = True,
    try_image_size: bool = True,
):
    get_size = None
    if try_image_size:
        try:
            from PIL import Image

            def _size_from_bytes(b: bytes):
                with Image.open(io.BytesIO(b)) as im:
                    return im.size  # (w, h)

            get_size = _size_from_bytes
        except Exception:
            get_size = None

    logging.info("=== message preview ===")
    logging.info(f"items: {len(message_content)}")
    for i, item in enumerate(message_content):
        t = item.get("type")
        if t == "text":
            text = str(item.get("text", ""))
            shown = text[:text_preview].replace("\n", "\\n")
            more = " …" if len(text) > text_preview else ""
            logging.info(f"[{i}] type=text chars={len(text)}")
            logging.info(f'     "{shown}"{more}')
        elif t == "image_url":
            url = item.get("image_url", {}).get("url", "")
            if url.startswith("data:"):
                mime, b64 = _parse_data_uri(url)
                bcount = _b64_bytes_len(b64)
                sha = ""
                size_str = ""
                try:
                    raw = base64.b64decode(b64, validate=False)
                    if show_sha:
                        sha = hashlib.sha1(raw).hexdigest()[:10]
                    if get_size:
                        try:
                            w, h = get_size(raw)
                            size_str = f" size={w}x{h}"
                        except Exception:
                            size_str = ""
                except Exception:
                    pass
                sha_str = f" sha1={sha}" if sha else ""
                logging.info(
                    f"[{i}] type=image_url mime={mime} bytes={bcount}{size_str}{sha_str}"
                )
            else:
                # 远程 URL 的情况
                logging.info(f"[{i}] type=image_url url={url}")
        else:
            logging.info(f"[{i}] type={t} (unrecognized) keys={list(item.keys())}")
    logging.info("=== end preview ===")


def image_to_base64(image_path: str):
    """
    从文件路径获取图片，转为base64
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def encode_file_to_data_uri(file_path: str) -> str:
    """
    Encode an image file to a data URI suitable for OpenAI-style image inputs.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Unsupported or unknown image format: {file_path}")

    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_string}"


def get_json_array_element(path: str, id: int):
    """
    从json文件读取一个数组，返回指定索引处的元素
    """

    # 暂时不考虑异常处理
    with open(
        path,
        "rb",
    ) as json_file:
        data = json.load(json_file)
    element = data[id]
    return element


def create_question(element: dict, with_answer) -> str:
    ret = ""
    question = element.get("question")
    choices = element.get("choices")
    ans = element.get("answer")
    formatted_choices = []
    if choices:
        for i, item in enumerate(choices):
            letter = chr(ord("A") + i)
            formatted_choices.append(f"{letter}. {item}")
        ret = question + "\n\n" + "\n".join(formatted_choices)
    else:
        ret = question
    if with_answer:
        ret = ret + "\n\n" + f"Answer: {ans}"
    return ret


def extract_python_code(text: str):
    # 匹配 ```python ... ``` 之间的内容
    if text.find("```python") == -1:
        return None
    match = re.search(r"```python(.*?)```", text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        return code
    return None


def install_missing_packages(code_string: str):
    # 匹配 import xxx 或 from xxx import
    imports = re.findall(
        r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)", code_string, re.MULTILINE
    )
    for pkg in set(imports):
        try:
            __import__(pkg)
        except ImportError:
            logging.info(f"自动安装缺失库: {pkg}")
            try:
                # 添加300秒超时保护
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg],
                    timeout=300,  # 5分钟超时
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logging.info(f"包安装失败: {pkg}, 错误: {result.stderr}")
            except subprocess.TimeoutExpired:
                logging.info(f"包安装超时: {pkg}，跳过安装")
            except Exception as e:
                logging.info(f"包安装异常: {pkg}, 错误: {e}")


def solve_text_only(
    init_image_base64: str, problem_statement: str, mode: str, model: str
):
    """
    let the llm solve the problem generating the reasoning steps and final answer all at once,
    rather than step by step with image generation in between.
    """
    logging.info("Starting text-only solving")

    # Use the text-only prompt template
    current_prompt = BASE_PROMPT_TEXT_ONLY
    current_prompt = current_prompt.replace("{problem_statement}", problem_statement)

    # Build message content for the LLM
    message_content = []
    message_content.append({"type": "text", "text": current_prompt})

    # Add the initial image if available
    if init_image_base64:
        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{init_image_base64}"},
            }
        )

    # Preview the message
    preview_message(message_content, text_preview=200)

    logging.info("Sending text-only request to the model")

    try:
        response_text = send_chat_with_retries(
            message_content,
            model=model,
            max_retries=5,
            initial_delay=1.0,
            backoff_factor=2.0,
        )
    except RuntimeError as e:
        logging.error(f"Text-only solving failed: {e}")
        return None

    response_text = extract_content(response_text)
    logging.info("Received model text-only response")
    logging.debug(f"Response content: {response_text}")

    return response_text


import re
import os


def preprocess_code_string(
    code_string: str, image_path: str, image_path_full: str
) -> str:
    """
    预处理代码字符串，强制重定向所有保存路径到 image_path_full
    """
    # 0. 路径预处理 (防止 Windows 路径的反斜杠在 Python 字符串中转义)
    # 使用 raw string 格式或转换斜杠
    safe_save_path = image_path_full.replace("\\", "/")

    # =======================================================
    # 核心修改：直接在代码最前面定义全局保存路径变量
    # 这样后续替换时，我们只需要替换成变量名，不用担心引号嵌套问题
    # =======================================================
    header_code = (
        f"import matplotlib\n"
        f"matplotlib.use('Agg')  # 强制非交互后端\n"
        f"import matplotlib.pyplot as plt\n"
        f"# 系统自动注入的保存路径\n"
        f"TARGET_SAVE_PATH = r'{safe_save_path}'\n"
    )

    # 如果代码里已经有 import matplotlib... 我们稍微清理一下避免重复(可选)，
    # 但最简单的方式是直接拼接到头部，Python 重复 import 没问题。
    modified_code = header_code + "\n" + code_string

    # 1. 替换 LaTeX 符号 (保持原有逻辑)
    modified_code = (
        modified_code.replace(r"\implies", "⇒")
        .replace(r"\therefore", "∴")
        .replace(r"\because", "∵")
    )

    # 2. 替换读取图片的 image_path (保持原有逻辑)
    if image_path:
        image_path_str = str(image_path).replace("\\", "/")
        modified_code = re.sub(
            r'(["\'])image_path(["\'])',
            lambda m: f"{m.group(1)}{image_path_str}{m.group(2)}",
            modified_code,
        )

    # 3. 移除交互式函数 (保持原有逻辑，稍微增强)
    interactive_patterns = [
        r"plt\.ginput\(.*?\)",
        r"input\(.*?\)",
        r"plt\.waitforbuttonpress\(.*?\)",
        r"plt\.pause\(.*?\)",
        r"plt\.show\(.*?\)",  # 包含 plt.show()
    ]
    for pattern in interactive_patterns:
        modified_code = re.sub(
            pattern, "# Interaction removed", modified_code, flags=re.DOTALL
        )

    # =======================================================
    # 4. 强力重写 savefig - 关键修改！
    # =======================================================
    # 策略：匹配 .savefig( 及其后的参数，直到遇到右括号
    # 无论里面是 'file.png' 还是 variable_name，统统替换为 TARGET_SAVE_PATH

    # 正则解释：
    # (\.|^)savefig  -> 匹配 .savefig 或 开头的 savefig
    # \s* -> 允许空格
    # \(             -> 匹配左括号
    # (?:[^)(]|\((?:[^)(]+|\([^)(]*\))*\))* -> 匹配括号内的内容（支持一层嵌套括号）
    # \)             -> 匹配右括号

    # 简易版（假设 LLM 不会在文件名里写括号）：
    savefig_pattern = r"(\.|^)savefig\s*\((.*?)\)"

    # 替换为使用我们注入的变量 TARGET_SAVE_PATH
    modified_code = re.sub(
        savefig_pattern,
        r"\1savefig(TARGET_SAVE_PATH)",
        modified_code,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # =======================================================
    # 5. 兜底保障
    # =======================================================
    # 如果正则没有找到任何 savefig（可能是 LLM 漏写了），手动添加一行
    if "TARGET_SAVE_PATH)" not in modified_code:
        # 检查是否有 matplotlib 引用，避免在无图代码中添加
        if "plt." in modified_code or "ax." in modified_code:
            modified_code += "\n\n# Auto-appended save command\ntry:\n    plt.savefig(TARGET_SAVE_PATH)\nexcept:\n    pass\n"

    return modified_code


def execute_and_capture_image(
    code_string: str,
    step_num: int,
    image_path: str = None,
    output_dir: str = "out_code",
) -> str:
    """
    执行代码并捕获生成的图像

    Args:
        code_string: 要执行的Python代码字符串
        step_num: 步骤编号，用于命名输出文件
        image_path: 输入图像路径
        output_dir: 输出目录

    Returns:
        str: 生成的图像路径，如果执行成功但无图像则返回"success_no_image"，失败返回空字符串
    """
    install_missing_packages(code_string)
    os.makedirs(output_dir, exist_ok=True)
    image_name = f"p{step_num}.png"
    image_path_full = (Path(output_dir) / image_name).as_posix()

    # 预处理代码字符串
    code_string = preprocess_code_string(code_string, image_path, image_path_full)

    # logging.info(f" EXECUTE CODE FOR STEP {step_num} ")
    # logging.info(code_string)

    exec_globals = {}
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    stdout_buf.seek(0)
    stdout_buf.truncate()
    stderr_buf.seek(0)
    stderr_buf.truncate()

    import signal
    import threading

    class TimeoutException(Exception):
        pass

    def timeout_handler(signum, frame):
        raise TimeoutException("代码执行超时")

    # 设置超时信号（仅在Unix系统上有效）
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(300)  # 5分钟超时
    except (AttributeError, ValueError):
        # Windows系统或信号不支持，使用线程超时
        pass

    try:
        if old_handler is not None:
            # Unix系统：使用信号超时
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(
                stderr_buf
            ):
                exec(code_string, exec_globals)
        else:
            # Windows系统：使用线程超时
            exec_result = []
            exec_exception = []

            def exec_with_timeout():
                try:
                    with contextlib.redirect_stdout(
                        stdout_buf
                    ), contextlib.redirect_stderr(stderr_buf):
                        exec(code_string, exec_globals)
                    exec_result.append(True)
                except Exception as e:
                    exec_exception.append(e)

            thread = threading.Thread(target=exec_with_timeout)
            thread.daemon = True
            thread.start()
            thread.join(timeout=300)  # 5分钟超时

            if thread.is_alive():
                raise TimeoutException("代码执行超时")

            if exec_exception:
                raise exec_exception[0]
            if not exec_result:
                raise RuntimeError("代码执行失败")

        # 检查是否生成了图片
        if os.path.exists(image_path_full):
            return image_path_full
        else:
            # 如果没有生成图片但代码执行成功，返回成功状态但不返回图片路径
            logging.info(f"代码执行成功但未生成图片: {image_path_full}")
            return "success_no_image"

    except TimeoutException as e:
        logging.info(f"代码执行超时: {e}")
        return ""
    except Exception:
        tb = traceback.format_exc()
        out = stdout_buf.getvalue()
        err = stderr_buf.getvalue()
        full_error = "\n".join(
            [
                ("STDOUT:\n" + out) if out else "",
                ("STDERR:\n" + err) if err else "",
                "TRACEBACK:\n" + tb,
            ]
        )
        raise RuntimeError(full_error)
    finally:
        # 恢复原始信号处理器
        if old_handler is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def parse_llm_response(response: str, mode: str) -> str | None:
    """
    解析LLM的回答, 获取text和code, 兼容有无 ** 包裹的情况
    """
    if mode == "code":
        return extract_python_code(response)
    elif mode in ("banana", "qwen"):
        desc_match = re.search(
            r"(?:\*\*)?Step \d+ \(Action Description\):(?:\*\*)?(.*?)(?=(?:\*\*)?Step|\Z)",
            response,
            re.DOTALL,
        )
        if desc_match:
            action_desc = desc_match.group(1).strip()
            if action_desc:
                return action_desc

        # 尝试提取 ```json ... ```
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            if json_content:
                return json_content

        return None
    else:
        return None


def generate_image_banana(
    description: str, output_path: str, init_image_path: str, images_path: list[str]
) -> str | None:
    logging.info(" START GENERATE IMAGE USING NANO BANANA ")
    delta = random.uniform(-0.5, 0.5) * SLEEP_TIME
    delay = SLEEP_TIME + delta
    time.sleep(delay)
    img = Image.open(init_image_path)
    contents = [img, description]

    max_attempts = 5

    for attempt in range(1, max_attempts + 1):
        try:
            response = banana_client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=contents,
            )
            for part in response.parts:
                if part.text is not None:
                    logging.info(f"Response text: {part.text}")
                elif part.inline_data is not None:
                    image = part.as_image()
                    image.save(output_path)
                    logging.info(f"\n SAVE IMAGE: {output_path} \n")
                    return output_path

            # 如果没有找到图片数据
            logging.warning(f"Attempt {attempt}: No image data found in response parts")
            sleep_time = delay * (2 ** (attempt - 1))
            logging.warning(f"Retrying in {sleep_time:.1f}s ...")
            time.sleep(sleep_time)
            continue

        except Exception as e:
            if "model_not_found" in str(e) or "503" in str(e):
                logging.warning(f"请求失败（{e}），第 {attempt} 次重试...")
                if attempt < max_attempts:
                    logging.warning(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    logging.warning("已达到最大重试次数，终止。")
                    return None
            else:
                logging.warning(
                    f"generate_image_banana attempt {attempt} failed: {type(e).__name__}: {e}"
                )
                if attempt == max_attempts:
                    logging.warning(
                        "!!! Max attempts reached, giving up on image generation !!!"
                    )
                    return None
                sleep_time = delay * (2 ** (attempt - 1))
                logging.warning(f"Retrying in {sleep_time:.1f}s ...")
                time.sleep(sleep_time)

    return None

def generate_image_qwen(
    description: str, output_path: str, init_image_path: str, images_path: list[str]
) -> str | None:
    logging.info(" START GENERATE IMAGE USING QWEN IMAGE EDIT ")
    
    # 检查是否有本地 API 地址 ===
    # 你可以通过环境变量设置，或者直接在这里写死 "http://localhost:8001/edit"
    local_api_url = os.environ.get("LOCAL_QWEN_API", "http://localhost:8001/edit")
    
    # 简单判断端口是否开放，或者直接默认使用本地服务
    use_local = True 
    
    if use_local:
        logging.info(f" Calling Local Model Server: {local_api_url}")
        try:
            # 1. 读取图片并转 Base64
            with open(init_image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            
            # 2. 构造请求 Payload
            payload = {
                "image_base64": img_b64,
                "prompt": description,
                "num_inference_steps": 20 # 或者从 args 获取
            }
            
            # 3. 发送 POST 请求
            response = requests.post(local_api_url, json=payload, timeout=600) # 图片生成可能较慢，设置长超时
            response.raise_for_status()
            
            # 4. 解析结果
            res_json = response.json()
            if "image_base64" in res_json:
                save_data = base64.b64decode(res_json["image_base64"])
                with open(output_path, "wb") as f:
                    f.write(save_data)
                logging.info(f"\n SAVE IMAGE (LOCAL): {output_path} \n")
                return output_path
            else:
                logging.error(f"Local API did not return image data: {res_json}")
                return None

        except Exception as e:
            logging.error(f"Failed to call local Qwen server: {e}")
            logging.info("Fallback to original remote logic (if configured)...")
            # 如果本地调用失败，你可以选择在这里 return None 或者让它继续走下面的远程逻辑
            # return None 
    
    # === 下面是原来的逻辑 (保留作为备份) ===
    image_refs = [str(init_image_path)]
    return _request_qwen_image_edit(
        description, image_refs, output_path, log_prefix="qwen image generation"
    )


def extract_content(response: str):
    # 1. 先去除 think 内容
    response = strip_think(response).strip()
    
    # 2. 增强版 Markdown 去除
    # 匹配开头可能包含语言标识的代码块标记，例如 ```json, ```markdown, 或仅仅 ```
    # re.sub 的逻辑是：找到开头的 ```... 换行符，替换为空
    if response.startswith("```"):
        # 去除首行的 ```language
        response = re.sub(r"```[a-zA-Z0-9]*\n", "", response)
        # 去除尾部的 ```
        if response.endswith("```"):
            response = response[:-3]
            
    return response.strip()


def strip_think(text: str) -> str:
    # 1. 预编译正则（提升性能）
    # 去除零宽字符 (保持你原有的逻辑)
    ZERO_WIDTH = re.compile(r"[\u200B-\u200D\uFEFF]")
    
    # 匹配结束标签 </think>，允许空白和大小写，例如 </ think >
    THINK_END = re.compile(r"<\s*/\s*think\s*>", re.IGNORECASE)
    
    # 2. 清理零宽字符
    text = ZERO_WIDTH.sub("", text)
    
    # 3. 核心逻辑更改：使用 Split 而不是 Sub
    # 我们只关心 </think> 之后的内容。
    # re.split 会根据正则将字符串切分。
    parts = THINK_END.split(text)
    
    # 如果切割出了多份，说明存在 </think>。
    # 我们取 parts[-1] (最后一部分)，这能确保：
    # (a) 只有 </think> 没有 <think> -> 丢弃前半部分，保留后半部分 (符合你的需求)
    # (b) <think>...</think> 成对 -> 丢弃前半部分(含思考)，保留后半部分
    # (c) 模型抽风输出了多个 </think> -> 我们只取最后一个标签之后的内容，通常是最安全的
    if len(parts) > 1:
        return parts[-1]
        
    # 如果没有找到 </think>，原样返回 (或者你可以选择用旧正则再次尝试匹配纯 <think> 开头的情况，但通常没必要)
    return text


def send_chat_with_retries(
    message_content,
    model="gpt-4o",
    max_retries=5,
    initial_delay=1.0,
    backoff_factor=2.0,
):
    """
    调用 openai_client.chat.completions.create，发生超时/连接错误时进行重试（指数退避）。
    返回模型响应对象，重试失败会抛出最后一次异常。
    """
    time.sleep(SLEEP_TIME)
    delay = initial_delay
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = openai_client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": message_content}]
            )
            # logging.info(f" resp \n{resp}")
            return resp.choices[0].message.content
        except Exception as e:
            last_exc = e
            logging.info(
                f"!!! Request failed (attempt {attempt}/{max_retries}): {e} !!!"
            )
            if attempt == max_retries:
                logging.info("!!! Max retries reached, re-raising exception !!!")
                raise
            sleep_time = delay * (backoff_factor ** (attempt - 1))
            logging.info(f"Retrying in {sleep_time:.1f}s ...")
            time.sleep(sleep_time)
    raise RuntimeError(last_exc)


def create_message_for_banana(descriptions: list[str], question: str):
    formatted_descs = []
    if descriptions:
        for i, desc in enumerate(descriptions):
            formatted_descs.append(f"{i + 1}. {desc}")
    # prompt = GENERATE_IMAGE_PROMPT.format(
    #     problem=question,
    #     descriptions="\n".join(formatted_descs),
    #     N=len(formatted_descs),
    # )
    prompt = GENERATE_IMAGE_PROMPT.replace("{json_instructions}", descriptions[-1] if descriptions else "")
    logging.info(f"Prompt for generate image: {prompt}")
    return prompt


def read_golden_file(golden_path: str) -> str:
    """Read golden file content"""
    with open(golden_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_interference_with_gpt(
    golden_content: str, problem: str, interference_type: str, model: str = "gpt-4o"
) -> str:
    """Generate interference using GPT-4o based on golden content"""

    if interference_type == "modify_key":
        type_desc = "modify key areas in the image"
    elif interference_type == "modify_non_key":
        type_desc = "modify background or non-key information"
    else:
        raise ValueError(f"Unknown interference type: {interference_type}")

    prompt = INTERFERENCE_PROMPT.format(
        problem=problem, golden_content=golden_content, interference_type=type_desc
    )

    message_content = [{"type": "text", "text": prompt}]

    response = send_chat_with_retries(
        message_content,
        model=model,
        max_retries=5,
        initial_delay=1.0,
        backoff_factor=2.0,
    )

    return extract_content(response)


def generate_image_interference(
    image_path: str,
    problem: str,
    interference_type: str,
    output_path: str,
    mode: str = "banana",
) -> str | None:
    """Generate image interference using banana or local qwen image edit."""
    logging.info(f" START IMAGE INTERFERENCE ({interference_type}) ")
    time.sleep(SLEEP_TIME)

    # Load the original image
    original_image = Image.open(image_path)

    # Create the interference prompt
    if interference_type == "modify_key":
        type_desc = "modify key areas in the image so that it produces errors or misleading information in important aspects that affect problem solving"
    elif interference_type == "modify_non_key":
        type_desc = "modify background or non-key information in the image, keeping the important information correct but creating interference in secondary details"
    else:
        raise ValueError(f"Unknown interference type: {interference_type}")

    prompt = IMAGE_INTERFERENCE_PROMPT.format(
        problem=problem, interference_type=type_desc
    )

    if mode == "qwen":
        logging.info("Using qwen image edit backend for interference")
        refs = [str(image_path)]
        qwen_result = _request_qwen_image_edit(
            prompt, refs, output_path, log_prefix="qwen image interference"
        )
        if qwen_result:
            return qwen_result
        logging.warning("Qwen interference failed; falling back to nano banana")

    contents = [prompt, original_image]

    max_attempts = 4
    delay = 2.0
    for attempt in range(1, max_attempts + 1):
        try:
            response = banana_client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=contents,
                config=types.GenerateContentConfig(response_modalities=["Image"]),
            )

            if not response or not response.candidates:
                logging.info(
                    f"Image interference attempt {attempt}: No candidates returned."
                )
                continue

            for part in response.parts:
                if part.text is not None:
                    logging.info(part.text)
                elif part.inline_data is not None:
                    interfered_image = part.as_image()
                    interfered_image.save(output_path)
                    logging.info(f" SAVE INTERFERED IMAGE: {output_path} ")
                    return output_path

        except Exception as e:
            logging.info(f"Image interference attempt {attempt} failed: {e}")
            if attempt == max_attempts:
                logging.info(
                    "!!! Max attempts reached for image interference, giving up !!!"
                )
                return output_path
            sleep_time = delay * (2 ** (attempt - 1))
            logging.info(f"Retrying image interference in {sleep_time:.1f}s ...")
            time.sleep(sleep_time)

    return output_path


def init_llm():
    global openai_client, banana_client, qwen_image_edit_client
    try:
        openai_client, backend_meta = _create_chat_client_from_env()
        logging.info(
            "LLM backend configured: %s (base_url=%s, api_key=%s)",
            backend_meta["backend"],
            backend_meta["base_url"],
            backend_meta["api_key_source"],
        )
    except Exception as e:
        logging.error(f"Failed to configure LLM backend: {e}")
        sys.exit(1)

    # Nano Banana认证信息
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_BASE_URL = os.environ.get("GEMINI_BASE_URL")
    if GEMINI_API_KEY == "" or GEMINI_BASE_URL == "":
        logging.info("GEMINI_API_KEY or GEMINI_BASE_URL not found")
        exit(1)
    logging.info(GEMINI_API_KEY)
    logging.info(GEMINI_BASE_URL)
    global banana_client
    banana_client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            base_url=GEMINI_BASE_URL,
        ),
    )

    try:
        qwen_image_edit_client, qwen_meta = _create_qwen_image_edit_client_from_env()
        if qwen_image_edit_client:
            service_type = (
                "online" if "https" in qwen_meta["base_url"] else "local/custom"
            )
            logging.info(
                "Qwen image edit client configured (%s service, base_url=%s, api_key=%s)",
                service_type,
                qwen_meta["base_url"],
                "configured" if qwen_meta["api_key_set"] else "using placeholder",
            )
        else:
            logging.info(
                "QWEN_IMAGE_EDIT_BASE_URL not set; qwen image edit generation disabled"
            )
    except Exception as e:
        qwen_image_edit_client = None
        logging.warning(f"Failed to initialize Qwen image edit client: {e}")


def get_current_prompt(
    mode: str, optional: bool, problem_statement: str, previous_steps_str: str
) -> str:
    if mode == "code":
        if not optional:
            current_prompt = BASE_PROMPT_CODE
        else:
            current_prompt = BASE_PROMPT_OPTIONAL_CODE
    elif mode in ("banana", "qwen"):
        if not optional:
            current_prompt = BASE_PROMPT_ACTION_JSON
        else:
            current_prompt = BASE_PROMPT_OPTIONAL_ACTION_JSON
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    current_prompt = current_prompt.replace("{problem_statement}", problem_statement)
    current_prompt = current_prompt.replace("{previous_steps}", previous_steps_str)
    return current_prompt


def main(
    path,
    id,
    output_dir,
    mode,
    model,
    with_answer: bool,
    max_steps: int,
    text_only: bool,
    step_wise_context: bool,
    interference: str = None,
    use_edge: bool = False,
    use_depth: bool = False,
    optional: bool = False,
):
    init_llm()
    # 如果目录存在且不为空，则清空
    output_dir = Path(output_dir)
    if output_dir.exists() and any(Path(output_dir).iterdir()):
        logging.info(f"CLEAR CONTENT UNDER: {output_dir}")
        for item in Path(output_dir).iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    # 如果目录不存在，创建该目录
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    element = get_json_array_element(path, id)

    problem_statement = create_question(element, with_answer)
    problem_statement_with_answer = create_question(element, with_answer=True)

    logging.info("\n SOLVING PROBLEM \n")
    logging.info(problem_statement)
    if element["image_path"] is None or element["image_path"] == "":
        logging.info(f"Error: No image_path in the problem data.")
        return
    init_image_path = Path(path).parent / element["image_path"]
    image_file_name = Path(element["image_path"]).name

    # we will change the init_image_path if use_edge or use_depth is true
    if use_edge:
        init_image_path = (
            Path(init_image_path).parent / constant.EDGE_DIR / image_file_name
        )
        if not init_image_path.exists():
            convert_image.convert_to_edge(
                str(Path(path).parent / element["image_path"]),
                str(init_image_path),
            )
    if use_depth:
        init_image_path = (
            Path(init_image_path).parent / constant.DEPTH_DIR / image_file_name
        )
        if not init_image_path.exists():
            convert_image.convert_to_depth(
                str(Path(path).parent / element["image_path"]),
                str(init_image_path),
            )

    if not init_image_path.exists():
        logging.info(f"Error: Image for problem not found at {init_image_path}")
        return

    # 保存问题和图片
    with open(Path(output_dir) / "q.md", "w", encoding="utf-8") as f:
        f.write(problem_statement_with_answer + "\n\n![](p0.png)")
    Image.open(init_image_path).save(Path(output_dir) / "p0.png")

    step_counter = 1
    step_outputs = []  # 记录LLM的回答，markdown格式
    images_path = []  # 记录图片路径
    generated_image_b64 = []  # 记录通过运行代码生成图片的base64编码
    descriptions = []  # 记录通过banana生成图片的描述

    initial_image_b64 = image_to_base64(init_image_path)
    images_path.append(init_image_path)
    steps_md_path = Path(output_dir) / "steps.md"

    if text_only:
        final_response = solve_text_only(
            initial_image_b64, problem_statement, mode, model
        )
        if final_response:
            with open(steps_md_path, "w", encoding="utf-8") as f:
                f.write(final_response + "\n")
            logging.info(f" steps saved to {steps_md_path} ")
        return

    while step_counter <= max_steps:
        logging.info(f"\n STEP {step_counter} \n")
        # 通过换行符连接数组中的元素

        # 修改，如果step_wise_context为true，只传入上一步的文本
        if not step_wise_context:
            logging.info(f"* give {len(step_outputs)} steps")
            previous_steps_str = (
                "\n".join(step_outputs) if step_outputs else "No steps taken yet"
            )
        else:
            if len(step_outputs) > 0:
                logging.info(f"* give one step: step_{len(step_outputs)}")
            previous_steps_str = step_outputs[-1] if len(step_outputs) > 0 else ""
        # 构建提示词
        current_prompt = get_current_prompt(
            mode=mode,
            # optional=optional,
            optional=True, # always use optional prompt to give model more freedom
            problem_statement=problem_statement,
            previous_steps_str=previous_steps_str,
        )

        # 构建发送给大模型的文本消息
        message_content = []
        message_content = [{"type": "text", "text": current_prompt}]

        # 添加图片：最开始的时候给原题的图片
        if len(step_outputs) == 0 or (not step_wise_context and not text_only):
            message_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{initial_image_b64}"},
                }
            )

        # 添加生成的图片
        if not text_only:
            if not step_wise_context:
                # 添加所有生成的图片
                for img_b64 in generated_image_b64:
                    message_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        }
                    )
            else:
                # 只添加最后一张图片
                if len(generated_image_b64) > 0:
                    message_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{generated_image_b64[-1]}"
                            },
                        }
                    )
        # 调用模型
        preview_message(message_content, text_preview=200)
        logging.info(" SENDING REQUEST TO THE MODEL ")
        try:
            response_text = send_chat_with_retries(
                message_content,
                model=model,
                max_retries=5,
                initial_delay=1.0,
                backoff_factor=2.0,
            )
        except RuntimeError as e:
            break
        response_text = extract_content(response_text)
        # response_text:str = response.choices[0].message.content
        logging.info(f" MODEL RESPONSE \n{response_text}")
        with open(steps_md_path, "a", encoding="utf-8") as f:
            # append 模式，
            # 如果后续步骤出现错误或者异常，保证可以及时保存中间数据
            # 如果没有错误或者异常，则被后续的write模式覆盖
            f.write(response_text + "\n\n")

        new_image_path = ""
        if mode == "code":
            # 解析LLM的回答
            code_to_execute = parse_llm_response(response_text, mode)

            # 运行代码，获取生成图片的路径
            retry_count = 0
            if code_to_execute:
                while retry_count < MAX_IMAGE_RETRY:
                    logging.info(" start create image ")
                    try:
                        if code_to_execute:
                            new_image_path = execute_and_capture_image(
                                code_to_execute,
                                step_counter,
                                init_image_path,
                                output_dir,
                            )
                            break
                        else:
                            retry_count += 1
                            continue
                    except RuntimeError as e:
                        retry_count += 1
                        logging.info(f"exception: {e}")
                        prompt = (
                            "fix the code, the error message is: "
                            f"{e}. {code_to_execute}, give me the corrected code only, no other text. the code must be wrapped in ```python...``` block"
                        )
                        logging.info(f" ask {model} to solve the code error ")
                        new_code = extract_python_code(
                            extract_content(
                                send_chat_with_retries(
                                    prompt,
                                    model,
                                    max_retries=5,
                                    initial_delay=1.0,
                                    backoff_factor=2.0,
                                )
                            )
                        )
                        code_to_execute = new_code if new_code else code_to_execute
                        logging.info(" corrected code ")
                        logging.info(code_to_execute)
        elif mode in ("banana", "qwen"):
            description = parse_llm_response(response_text, mode)
            descriptions.append(description)
            if description:
                # 调用banana生成图片并保存
                image_name = f"p{step_counter}.png"
                image_path_full = (Path(output_dir) / image_name).as_posix()
                image_prompt = create_message_for_banana(
                    descriptions, problem_statement
                )
                if mode == "banana":
                    new_image_path = generate_image_banana(
                        image_prompt,
                        image_path_full,
                        init_image_path,
                        images_path,
                    )
                else:
                    new_image_path = generate_image_qwen(
                        image_prompt,
                        image_path_full,
                        init_image_path,
                        images_path,
                    )
            else:
                logging.info("find no description for image generation, so skip")
        else:
            return
        if new_image_path:
            logging.info(f" generate {new_image_path} ")

            # Apply interference to generated image if interference is enabled and conditions are met
            if interference:
                should_interfere = False

                # Define interference conditions
                if step_counter % 3 == 0:  # 每3步
                    should_interfere = True
                    reason = f"step {step_counter} (every 3rd step)"
                elif step_counter == 1:  # 第1步
                    should_interfere = True
                    reason = f"step {step_counter} (first step)"

                if should_interfere:
                    logging.info(
                        f" APPLYING INTERFERENCE TO GENERATED IMAGE ({interference}) - {reason} "
                    )
                    interfered_gen_path = generate_image_interference(
                        new_image_path,
                        problem_statement,
                        interference,
                        new_image_path,  # Overwrite the original generated image
                        mode=mode,
                    )

                    if interfered_gen_path:
                        logging.info(
                            f" INTERFERENCE APPLIED TO GENERATED IMAGE ({reason}) "
                        )
                    else:
                        logging.info(
                            f" INTERFERENCE FAILED FOR GENERATED IMAGE ({reason}) "
                        )

            images_path.append(new_image_path)
            new_image_b64 = image_to_base64(new_image_path)
            generated_image_b64.append(new_image_b64)
        else:
            logging.info(f" not generate {new_image_path} ")
        step_outputs.append(response_text)
        step_counter += 1

        # 判断是否结束
        if "Final Answer:" in response_text.strip():
            logging.info(" Final Answer Received ")
            if response_text.strip() != step_outputs[-1].strip():
                step_outputs.append(response_text)
            break

    with open(steps_md_path, "w", encoding="utf-8") as f:
        for idx, step in enumerate(step_outputs):
            if idx == (len(step_outputs) - 1):
                f.write(f"{step}\n")
            else:
                f.write(f"{step}\n\n![](p{idx+1}.png)\n\n")
    logging.info(f" steps saved to {steps_md_path} ")


if __name__ == "__main__":
    """
    example:
    python3 auto_solve.py -p annotation/dataset/data/m3cot/test1/data.json -i 20 -o tasks/out/m3cot/test1/20/ -m banana -M gemini-2.5-pro
    """
    parser = argparse.ArgumentParser(
        description=(
            "自动推理并保存图片和步骤。示例：\n\n"
            "python3 auto_solve.py -p annotation/dataset/data/m3cot/test1/data.json"
            " -i 20 -o tasks/out/m3cot/test1/20/ -m banana -M gemini-2.5-flash"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-p", "--path", type=str, required=True, help="json数据文件路径"
    )
    parser.add_argument(
        "-i", "--id", type=int, required=True, help="问题在json数组中的索引"
    )
    parser.add_argument(
        "-o", "--output_dir", type=str, required=True, help="图片和步骤保存目录"
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        required=True,
        default="code",
        help=(
            "回答模式："
            "code 表示让模型输出 python 代码，"
            "banana 表示调用 nano banana (gemini-2.5-flash-image) 绘图，"
            "qwen 表示调用 qwen-image-edit 服务进行图像编辑"
        ),
    )
    parser.add_argument(
        "-M",
        "--model",
        type=str,
        required=True,
        help="选择模型，如gpt-5, gemini-2.5-flash",
    )
    parser.add_argument(
        "--with_answer",
        action="store_true",
        help="是否在提问时附加答案（默认不附加答案）",
    )
    parser.add_argument(
        "--max_steps",
        type=int,
        default=10,
        help="允许的最长推理步骤数（默认值为10）",
    )
    parser.add_argument(
        "--step_wise_context",
        action="store_true",
        help="是否仅传入题目和上一步的推理结果（默认传入所有步骤）",
    )

    exp_exclusive_group = parser.add_mutually_exclusive_group()
    exp_exclusive_group.add_argument(
        "--text_only",
        action="store_true",
        help="仅使用文本进行推理，不生成图片",
    )
    exp_exclusive_group.add_argument(
        "--interference",
        type=str,
        choices=["modify_key", "modify_non_key"],
        help="对生成的图片进行干扰：modify_key（修改关键区域）或 modify_non_key（修改非关键区域）",
    )
    parser.add_argument(
        "--use_edge",
        action="store_true",
        help="使用边缘图作为初始图片（默认使用原始图片）",
    )
    parser.add_argument(
        "--use_depth",
        action="store_true",
        help="使用深度图作为初始图片（默认使用原始图片）",
    )
    parser.add_argument(
        "--optional",
        action="store_true",
        help="使用可选的提示模板（base_prompt_optional_code 或 base_prompt_optional_action_json）",
    )
    args = parser.parse_args()
    logging.info(json.dumps(vars(args), ensure_ascii=False, indent=2))

    main(
        args.path,
        args.id,
        args.output_dir,
        args.mode,
        args.model,
        args.with_answer,
        args.max_steps,
        args.text_only,
        args.step_wise_context,
        args.interference,
        use_depth=args.use_depth,
        use_edge=args.use_edge,
        optional=args.optional,
    )
