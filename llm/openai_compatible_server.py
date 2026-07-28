import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from huggingface_hub import snapshot_download
import uvicorn
import json
import base64
from io import BytesIO
from PIL import Image
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time


# OpenAI兼容的数据模型
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "qwen-vl"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    stream: Optional[bool] = False


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict]
    usage: Dict


class OpenAICompatibleServer:
    def __init__(self, model_name="Qwen/Qwen2-VL-7B-Instruct"):
        self.app = FastAPI(title="Qwen VL OpenAI兼容API")
        self.model_name = model_name
        self.setup_routes()
        self.setup_model()

    def setup_model(self):
        """初始化模型"""
        print("正在加载Qwen视觉模型...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # start fast download from HF Hub
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER_API", "1")
        cache_dir = os.environ.get(
            "TRANSFORMERS_CACHE",
            os.environ.get("TRANSFORMERS_CACHE", "~/.cache/huggingface"),
        )
        cache_dir = os.path.expanduser(cache_dir)

        repo_dir = None
        try:
            print("downloading model to cache:", cache_dir)
            repo_dir = snapshot_download(
                repo_id=self.model_name,
                cache_dir=cache_dir,
                max_workers=16,
                resume_download=True,
            )
            print("model downloaded to:", repo_dir)
        except Exception as e:
            print("snapshot_download failed:", str(e))
            repo_dir = self.model_name

        # load from local cache dir or downloaded repo dir
        self.processor = AutoProcessor.from_pretrained(repo_dir, trust_remote_code=True)

        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            repo_dir,
            dtype=dtype,
            trust_remote_code=True,
        )

        # 手动将模型移动到指定设备
        if self.device == "cuda":
            self.model = self.model.cuda()
        else:
            self.model = self.model.cpu()
        print("模型加载完成!")

    def setup_routes(self):
        """设置API路由"""

        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: ChatCompletionRequest):
            """OpenAI兼容的聊天补全接口"""
            try:
                response = await self.process_chat_request(request)
                return response
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/v1/models")
        async def list_models():
            """列出可用模型"""
            return {
                "object": "list",
                "data": [
                    {
                        "id": "qwen-vl",
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "self-deployed",
                    }
                ],
            }

        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy"}

    async def process_chat_request(self, request: ChatCompletionRequest):
        """处理聊天请求"""
        # 提取文本和图片信息
        messages = request.messages
        text_content = ""
        image = None

        for msg in messages:
            if msg.role == "user":
                # 解析内容，支持混合内容类型
                if isinstance(msg.content, str):
                    # 简单文本处理
                    text_content = msg.content
                elif isinstance(msg.content, list):
                    # 多模态内容处理
                    for content_item in msg.content:
                        if content_item.get("type") == "text":
                            text_content = content_item.get("text", "")
                        elif content_item.get("type") == "image_url":
                            # 处理base64图片
                            image_url = content_item.get("image_url", {}).get("url", "")
                            if image_url.startswith("data:image"):
                                # base64图片
                                image_data = image_url.split(",")[1]
                                image = Image.open(
                                    BytesIO(base64.b64decode(image_data))
                                )
                            else:
                                # 网络图片URL
                                import requests

                                response = requests.get(image_url)
                                image = Image.open(BytesIO(response.content))

        if not text_content:
            raise HTTPException(status_code=400, detail="未找到文本内容")

        if not image:
            raise HTTPException(status_code=400, detail="未找到图片内容")

        # 调用模型生成回复
        response_text = await self.generate_response(image, text_content, request)

        # 构建OpenAI兼容的响应
        response_id = f"chatcmpl-{int(time.time())}"

        return ChatCompletionResponse(
            id=response_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            usage={
                "prompt_tokens": 0,  # 实际使用时可以计算真实token数
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )

    async def generate_response(self, image, text, request):
        """调用模型生成回复"""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": text},
                ],
            }
        ]

        # 处理输入
        text_prompt = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.processor(
            text=[text_prompt], images=[image], padding=True, return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 生成配置
        generation_config = {
            "max_new_tokens": request.max_tokens or 512,
            "do_sample": request.temperature > 0,
        }

        if request.temperature > 0:
            generation_config["temperature"] = request.temperature
        if request.top_p:
            generation_config["top_p"] = request.top_p

        # 生成回复
        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, **generation_config)

        # 解码输出
        generated_ids_trimmed = generated_ids[:, inputs["input_ids"].shape[1] :]
        response = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True
        )[0]

        return response


# 启动服务
if __name__ == "__main__":
    server = OpenAICompatibleServer()
    uvicorn.run(server.app, host="0.0.0.0", port=8080)
