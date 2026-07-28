from diffusers import AutoPipelineForImage2Image, FlowMatchEulerDiscreteScheduler
from diffusers.utils import load_image
import torch
import math
import os

# ================= 配置区域 =================
# 1. 设置 Base Model 的本地文件夹路径
#    例如: "/home/user/models/Qwen-Image-Edit-2509"
local_base_model_path = "/storage/v-jinpewang/yansiyu_workspace/See2Think/models/Qwen-Image-Edit-2509" 

# 2. 设置 Lightning LoRA 的本地路径
#    load_lora_weights 第一个参数通常是文件夹路径，第二个参数是文件名
local_lora_folder = "/storage/v-jinpewang/yansiyu_workspace/See2Think/models/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16"
lora_filename = "adapter_model.safetensors"

# 3. 设置输入图片路径
input_image_path = "input.png"
# ===========================================

# Scheduler 配置 (保持原样)
scheduler_config = {
    "base_image_seq_len": 256,
    "base_shift": math.log(3),
    "invert_sigmas": False,
    "max_image_seq_len": 8192,
    "max_shift": math.log(3),
    "num_train_timesteps": 1000,
    "shift": 1.0,
    "shift_terminal": None,
    "stochastic_sampling": False,
    "time_shift_type": "exponential",
    "use_beta_sigmas": False,
    "use_dynamic_shifting": True,
    "use_exponential_sigmas": False,
    "use_karras_sigmas": False,
}
scheduler = FlowMatchEulerDiscreteScheduler.from_config(scheduler_config)

print(f"正在从本地加载模型: {local_base_model_path} ...")

# 加载 Pipeline
# 注意：这里直接传入本地路径字符串
pipe = AutoPipelineForImage2Image.from_pretrained(
    local_base_model_path,
    scheduler=scheduler,
    torch_dtype=torch.bfloat16,
    use_safetensors=True  # 假设本地文件是 safetensors 格式
).to("cuda")

print(f"正在加载 LoRA: {lora_filename} ...")

# 加载本地 LoRA
# 第一个参数是存放 LoRA 的文件夹，weight_name 是具体的文件名
pipe.load_lora_weights(
    local_lora_folder, 
    weight_name=lora_filename
)

# 加载并处理输入图片
if not os.path.exists(input_image_path):
    raise FileNotFoundError(f"找不到输入图片: {input_image_path}")

init_image = load_image(input_image_path).resize((1024, 1024))

# 定义 Prompt
prompt = "A hand-drawn animated illustration of the friendly brown bear from image_0.png, rendered in a warm, cel-shaded cartoon style. The bear has a gentle, smiling expression with soft, large brown eyes looking slightly upwards. Its thick, shaggy brown fur is textured with bold outlines and warm color variations. The large, round ears and prominent black nose are distinctly cartoonish. The background is a lush, simplified forest with green cartoon trees, bushes, and sunlight filtering through the canopy, creating a cheerful and inviting scene. The overall feel is that of a classic animated film."
negative_prompt = " "

print("开始生成...")

# 推理
image = pipe(
    prompt=prompt,
    image=init_image,          # 传入图片
    strength=0.75,             # 编辑强度 (0.1 微调 - 1.0 重绘)
    negative_prompt=negative_prompt,
    width=1024,
    height=1024,
    num_inference_steps=8,     # Lightning 模型保持低步数
    true_cfg_scale=1.0,
    generator=torch.manual_seed(0),
).images[0]

output_filename = "/storage/v-jinpewang/yansiyu_workspace/See2Think/qwen_edit_local.png"
image.save(output_filename)
print(f"完成！图片已保存为 {output_filename}")