import gc
from pathlib import Path
import sys
import uvicorn
import base64
import io
import torch
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from PIL import Image
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

project_root = Path(current_dir).parent.parent
default_model_base = project_root / "models"

local_models_base = os.environ.get("SEE2THINK_LOCAL_MODELS_BASE", str(default_model_base)).strip()
if not local_models_base:
    raise RuntimeError(
        "SEE2THINK_LOCAL_MODELS_BASE must be set to the directory containing Qwen-Image-Edit-2509"
    )

try:
    from vanillaPipeline import VanillaPipeline
except ImportError as e:
    raise RuntimeError(f"导入失败: {e}。请确保 vanillaPipeline.py 在 {current_dir} 目录下")

try:
    from wrapped_tools import MultiGPUTransformer
except ImportError:
    raise RuntimeError(f"缺少wrapped_tools.py")

models_base_path = Path(local_models_base).expanduser().resolve()
if not models_base_path.exists():
    raise RuntimeError(f"SEE2THINK_LOCAL_MODELS_BASE does not exist: {models_base_path}")

qwen_image_edit_2509 = str(models_base_path / "Qwen-Image-Edit-2509")

app = FastAPI(title="Qwen Image Edit Local API")

# 简单 Health endpoints，供外部脚本探测服务是否可用
@app.get("/")
async def root():
    return {"status": "ok", "service": "qwen-image-edit"}

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- 2. 全局加载模型 (启动时运行一次) ---
print("正在加载模型 Qwen-Image-Edit-2509 ...")
try:
    # 首先加载到CPU
    pipeline = VanillaPipeline.from_pretrained(
        qwen_image_edit_2509, 
        torch_dtype=torch.bfloat16,
        local_files_only=True
    ).to("cpu")
    
    lora = str(Path(local_models_base) / "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16/adapter_model.safetensors")
    
    if os.path.exists(lora):
        pipeline.load_lora_weights(lora, adapter_name="Lightning-8steps")
        pipeline.fuse_lora(lora_scale=1.0)
        print("LoRA加载融合完成！")
    else:
        print("没有加载LoRA")
    # 手动将小组件移动到GPU0
    print("Moving VAE and Text Encoder to GPU 0...")
    pipeline.vae.to("cuda:0")
    pipeline.text_encoder.to("cuda:0")

    # 使用 MultiGPUTransformer 切分并加载 Transformer
    # 自动检测有多少张显卡，将模型层平均分配到各个卡上
    print("Splitting Transformer across GPUs...")
    flux_transformer = MultiGPUTransformer(pipeline.transformer).auto_split()
    flux_transformer.eval()
    pipeline.transformer = flux_transformer

    pipeline.set_progress_bar_config(disable=None) # 服务端通常关闭进度条

    print("模型加载完成，服务准备就绪！")
except Exception as e:
    print(f"模型加载失败: {e}")
    if torch.cuda.is_available():
        print(f"当前显存占用：{torch.cuda.memory_allocated()/1024**3:2.f} GB")
    raise e

# --- 3. 定义数据结构 (兼容 OpenAI 多模态格式) ---
class ImageUrl(BaseModel):
    url: str  # 这里我们将传入 "data:image/png;base64,..."

class ContentItem(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None

class Message(BaseModel):
    role: str
    content: Union[str, List[ContentItem]]

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    # 允许客户端传递额外参数
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    force_fast_mode: Optional[bool] = True # 控制是否开启极速模式

# --- 4. 辅助函数：Base64 转 PIL ---
def decode_base64_image(base64_string):
    if "base64," in base64_string:
        base64_string = base64_string.split("base64,")[1]
    image_data = base64.b64decode(base64_string)
    return Image.open(io.BytesIO(image_data)).convert("RGB")

# --- 5. 辅助函数：PIL 转 Base64 ---
def encode_image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 6. API 接口定义 ---
@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    """
    模拟 OpenAI 多模态 Chat 接口
    """
    try:
        # 1. 解析输入：从 messages 中提取 Prompt 和 Images
        prompt = ""
        input_images = []
        
        # 遍历最后一条用户消息
        last_message = request.messages[-1]
        if isinstance(last_message.content, str):
            prompt = last_message.content
        elif isinstance(last_message.content, list):
            for item in last_message.content:
                if item.type == "text":
                    prompt += item.text
                elif item.type == "image_url":
                    img = decode_base64_image(item.image_url.url)
                    input_images.append(img)

        if len(input_images) == 0:
            return {"error": "该模型至少需要一张输入图片"}
        
        # 实施优化策略
        target_image = input_images[0]
        # TARGET_SIZE = 512
        # if request.force_fast_mode:
        #     print(f"调整图片大小为: {TARGET_SIZE}x{TARGET_SIZE}")
        #     target_image = target_image.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)

        # 开启CFG，防止模糊
        cfg_scale = 1.0
        # 负面提示词
        negative_prompt = "bounding box, red rectangle, text, words, letters, characters, labels, annotations, arrows, markers, highlights, sketches, borders, frames, outlines, watermarks, logos, signatures, captions, instructions, notes, diagrams, symbols, non-photorealistic elements, artifacts, residual traces, incomplete erasure, partial removal"

        # 计算面积
        current_area = target_image.width * target_image.height

        # 2. 构造模型输入参数
        inputs = {
            "image": target_image, 
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_inference_steps": 8,
            "generator": torch.Generator(device="cuda").manual_seed(42),

            "target_area": current_area,
            "true_cfg_scale": cfg_scale,
            "max_sequence_length": 1024,
        }

        print(f"开始推理: Prompt='{prompt}', Size={target_image.size}, FastMode={request.force_fast_mode}")

        start_time = time.time()
        print(f'infer start at {time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime(start_time))}')
        # 3. 执行推理
        # 使用 inference_mode 上下文
        with torch.inference_mode():
            output = pipeline(**inputs)
            if hasattr(output, "images"):
                output_image = output.images[0]
            else:
                output_image = output[0]
            output_image.save("/storage/v-jinpewang/yansiyu_workspace/See2Think/outputs/server_qwen_test_with_8_steps_lora.png")
            output_image.save("outputs/server_qwen_test_with_8_steps_lora.png")
        print("Image successfully saved to /storage/v-jinpewang/yansiyu_workspace/See2Think/outputs/server_qwen_test_with_8_steps_lora.png")
        
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        end_time = time.time()
        print(f'infer start at {time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime(end_time))}')
        elapsed_time = end_time - start_time
        print(f"图片生成耗时： {(elapsed_time / 60):.2f} 分")
        
        # 推理结束后，强制清理一波显存，防止碎片堆积
        torch.cuda.empty_cache()
        gc.collect()

        # 4. 结果编码
        output_base64 = encode_image_to_base64(output_image)

        # 5. 返回 OpenAI 兼容格式
        return {
            "id": "chatcmpl-local-fast",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": output_base64  # 这里我们将图片Base64直接放在内容里返回，或者可以使用特定的多模态返回格式
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "inference_time_second": elapsed_time
            },
        }

    except Exception as e:
        print(f"推理错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # 启动服务，监听 8000 端口
    uvicorn.run(app, host="0.0.0.0", port=8000)
