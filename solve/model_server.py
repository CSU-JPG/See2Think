# model_server.py
import torch
import uvicorn
import base64
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from io import BytesIO
from PIL import Image

from qwen_infer_plus import MyQwenImageEditPipeline, MultiGPUTransformer 

app = FastAPI(title="Local Qwen Image Edit Server")
pipeline = None

# 定义请求体结构
class GenerateRequest(BaseModel):
    image_base64: str
    prompt: str
    num_inference_steps: int = 20
    guidance_scale: float = 1.0
    true_cfg_scale: float = 4.0

@app.on_event("startup")
def load_model():
    global pipeline
    print(">>> 正在初始化模型到 GPU (4,5,6,7)...")
    
    model_path = "/storage/v-xiangxizheng/cache/Qwen-Image-Edit-2509" # 请确认路径
    
    # 1. 加载 Pipeline
    pipeline = MyQwenImageEditPipeline.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16
    )
    
    # 2. 执行你的多卡分配逻辑
    pipeline.transformer.to(torch.float32)
    pipeline.vae.to("cuda:0")
    pipeline.text_encoder.to("cuda:0")
    
    total_blocks = len(pipeline.transformer.transformer_blocks)
    gpu_split_points = [total_blocks//3, 2*total_blocks//3]
    
    print(f"分配策略: GPU1(Blocks 0-{gpu_split_points[0]-1}), GPU2(Blocks {gpu_split_points[0]}-{gpu_split_points[1]-1}), GPU3(剩余)")
    
    pipeline.transformer = MultiGPUTransformer(pipeline.transformer, gpu_split_points)
    pipeline.set_progress_bar_config(disable=True) # 服务端通常不需要进度条
    
    print(">>> 模型加载完成，服务就绪！")

@app.post("/edit")
async def edit_image(req: GenerateRequest):
    if not pipeline:
        raise HTTPException(status_code=500, detail="Model not initialized")
    
    try:
        # 1. Base64 -> PIL Image
        image_data = base64.b64decode(req.image_base64)
        input_image = Image.open(BytesIO(image_data)).convert("RGB")
        
        # 2. 推理
        generator = torch.Generator(device="cuda").manual_seed(42)
        
        with torch.inference_mode():
            output = pipeline(
                image=input_image,
                prompt=req.prompt,
                generator=generator,
                true_cfg_scale=req.true_cfg_scale,
                negative_prompt=" ", # 你的默认设置
                num_inference_steps=req.num_inference_steps,
                guidance_scale=req.guidance_scale
            )
            result_image = output.images[0]
        
        # 3. PIL Image -> Base64
        buffered = BytesIO()
        result_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return {"status": "success", "image_base64": img_str}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model loading")
    return {"status": "ok", "gpu": "ready"}

if __name__ == "__main__":
    # 指定显卡可见性，确保服务能看到 4 张卡
    # os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3"
    os.environ["CUDA_VISIBLE_DEVICES"] = "4,5,6,7"
    uvicorn.run(app, host="0.0.0.0", port=9000)