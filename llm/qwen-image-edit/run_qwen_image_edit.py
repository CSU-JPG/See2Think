import argparse
import math
import os
import torch
from PIL import Image

from diffusers import (
    DiffusionPipeline,
    FlowMatchEulerDiscreteScheduler,
    QwenImageEditPipeline,
    QwenImageEditPlusPipeline,
)
from diffusers.models import QwenImageTransformer2DModel

# def main(args):
#     # 1. 精度检测 (V100 使用 float16)
#     if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
#         print("BF16 supported, using bfloat16.")
#         torch_dtype = torch.bfloat16
#     else:
#         print("BF16 NOT supported (likely V100/T4), using float16.")
#         torch_dtype = torch.float16

#     print(f"Loading model from local path: {args.model_path}")
#     print("Using device_map='balanced' to spread model across GPUs.")

#     is_edit_plus = "2509" in args.model_path or args.force_plus
    
#     if is_edit_plus:
#         pipe_cls = QwenImageEditPlusPipeline
#         print("Using QwenImageEditPlusPipeline")
#     else:
#         pipe_cls = QwenImageEditPipeline
#         print("Using QwenImageEditPipeline")

#     # 2. 模型加载 (集成 device_map)
#     # 注意：使用 device_map 时，必须确保安装了 accelerate 库 (pip install accelerate)
    
#     if args.lora_path is not None:
#         print(f"Loading with LoRA from: {args.lora_path}")
        
#         # 调度器配置
#         scheduler_config = {
#             "base_image_seq_len": 256,
#             "base_shift": math.log(3),
#             "invert_sigmas": False,
#             "max_image_seq_len": 8192,
#             "max_shift": math.log(3),
#             "num_train_timesteps": 1000,
#             "shift": 1.0,
#             "shift_terminal": None,
#             "stochastic_sampling": False,
#             "time_shift_type": "exponential",
#             "use_beta_sigmas": False,
#             "use_dynamic_shifting": True,
#             "use_exponential_sigmas": False,
#             "use_karras_sigmas": False,
#         }
#         scheduler = FlowMatchEulerDiscreteScheduler.from_config(scheduler_config)
        
#         # 加载 Pipeline (使用 device_map="balanced", 不要传入 model=...)
#         pipe = pipe_cls.from_pretrained(
#             args.model_path, 
#             scheduler=scheduler, 
#             torch_dtype=torch_dtype, 
#             device_map="balanced"
#         )
#         pipe.load_lora_weights(args.lora_path)
        
#     else:
#         # 加载 Pipeline (使用 device_map="balanced")
#         pipe = pipe_cls.from_pretrained(
#             args.model_path, 
#             torch_dtype=torch_dtype, 
#             device_map="balanced"
#         )

#     # ========================== 终极修复 & 诊断代码 ==========================
#     import sys
    
#     # 1. 强制刷新打印缓冲区，保证日志顺序正确
#     sys.stdout.flush()
#     print("--- Starting VAE Patch & Diagnostics ---", flush=True)

#     if hasattr(pipe, "vae") and pipe.vae is not None:
#         # 【核心修复 1】禁用切片和平铺。这是解决黑图最有效的办法之一。
#         # 虽然会增加一点显存占用，但能大幅减少数值溢出。
#         try:
#             pipe.vae.disable_slicing()
#             pipe.vae.disable_tiling()
#             print(" -> Disabled VAE slicing and tiling (Fix for black images).", flush=True)
#         except Exception as e:
#             print(f" -> Warning: Could not disable slicing/tiling: {e}", flush=True)

#         # 【核心修复 2】强制 VAE 全精度 (FP32)
#         pipe.vae.to(dtype=torch.float32)
#         print(" -> Forced VAE to float32.", flush=True)

#         # 备份原始方法
#         if not hasattr(pipe.vae, "_original_encode"):
#             pipe.vae._original_encode = pipe.vae.encode
#         if not hasattr(pipe.vae, "_original_decode"):
#             pipe.vae._original_decode = pipe.vae.decode

#         # Patch Encode: FP32计算 -> 转回BF16输出
#         def new_encode(x, *args, **kwargs):
#             if x.dtype != torch.float32:
#                 x = x.to(torch.float32)
#             output = pipe.vae._original_encode(x, *args, **kwargs)
#             # 将分布参数转回 BF16，喂给 Transformer
#             if hasattr(output, "latent_dist"):
#                 dist = output.latent_dist
#                 if hasattr(dist, "mean") and dist.mean.dtype == torch.float32:
#                     dist.mean = dist.mean.to(dtype=torch.bfloat16)
#                 if hasattr(dist, "std") and dist.std.dtype == torch.float32:
#                     dist.std = dist.std.to(dtype=torch.bfloat16)
#                 if hasattr(dist, "logvar") and dist.logvar is not None:
#                     dist.logvar = dist.logvar.to(dtype=torch.bfloat16)
#             return output

#         # Patch Decode: 增加 NaN 检测
#         def new_decode(z, *args, **kwargs):
#             # 【诊断】检查 Transformer 输出的 Latents 是否已经坏了
#             if torch.isnan(z).any() or torch.isinf(z).any():
#                 print("!!! CRITICAL WARNING: Latents contain NaNs/Infs BEFORE decoding!", flush=True)
#                 print(" -> This means the Transformer (or LoRA) failed, not the VAE.", flush=True)
#             else:
#                 print(f" -> Latents statistics: Min={z.min().item():.3f}, Max={z.max().item():.3f} (Values look okay)", flush=True)

#             # 转 FP32 解码
#             if z.dtype != torch.float32:
#                 z = z.to(torch.float32)
#             return pipe.vae._original_decode(z, *args, **kwargs)

#         pipe.vae.encode = new_encode
#         pipe.vae.decode = new_decode
        
#         print("--- VAE Patch Applied Successfully ---", flush=True)
#     # ========================================================================

#     # 【关键点 2】删除 pipe.to(device)
#     # 既然用了 device_map，accelerate 会自动管理设备。
#     # 如果强行运行 pipe.to('cuda') 会报错或导致显存管理失效。
    
#     # 也不要使用 enable_model_cpu_offload，因为 device_map 已经把模型铺在显存里了
    
#     pipe.set_progress_bar_config(disable=None)

#     # 3. 数据准备
#     input_images = []
#     if args.image_paths:
#         for img_path in args.image_paths:
#             print(f"Loading image: {img_path}")
#             input_images.append(Image.open(img_path).convert("RGB"))
#     else:
#         raise ValueError("Please provide input images using --image_paths")

#     # 4. 参数配置
#     if args.steps is None:
#         num_inference_steps = 8 if args.lora_path else 50
#     else:
#         num_inference_steps = args.steps

#     if args.cfg is None:
#         true_cfg_scale = 1.0 if args.lora_path else 4.0
#     else:
#         true_cfg_scale = args.cfg

#     # 生成器建议放在 CPU 上，以避免多卡环境下的随机数设备冲突
#     generator = torch.Generator(device="cpu").manual_seed(args.seed)

#     inputs = {
#         "image": input_images,
#         "prompt": args.prompt,
#         "generator": generator,
#         "true_cfg_scale": true_cfg_scale,
#         "negative_prompt": args.negative_prompt,
#         "num_inference_steps": num_inference_steps,
#         "guidance_scale": 1.0,
#     }
    
#     # 单图且非 Plus 模式的尺寸处理（可选）
#     if not is_edit_plus and len(input_images) == 1:
#         pass

#     print(f"Start inference with prompt: '{args.prompt}'")
    
#     # 5. 执行推理
#     with torch.inference_mode():
#         output = pipe(**inputs)
#         output_image = output.images[0]

#     # 6. 保存
#     os.makedirs(args.out_dir, exist_ok=True)
#     save_path = os.path.join(args.out_dir, args.output_filename)
#     output_image.save(save_path)
#     print(f"Image saved successfully at: {os.path.abspath(save_path)}")


def main(args):
    # ============================================================
    # 1. 强制使用 Float32 (解决 Transformer NaN/Inf 问题)
    # ============================================================
    print("!!! Force using Float32 to prevent Transformer NaN overflow !!!")
    torch_dtype = torch.float32  # <--- 关键修改：不再检测 BF16，直接用 FP32

    print(f"Loading model from local path: {args.model_path}")
    print("Using device_map='balanced' to spread model across GPUs.")

    is_edit_plus = "2509" in args.model_path or args.force_plus
    
    if is_edit_plus:
        pipe_cls = QwenImageEditPlusPipeline
        print("Using QwenImageEditPlusPipeline")
    else:
        pipe_cls = QwenImageEditPipeline
        print("Using QwenImageEditPipeline")

    # ============================================================
    # 2. 模型加载
    # ============================================================
    
    # 建议：先尝试注释掉手动定义的 scheduler_config，让模型加载默认的配置
    # 很多时候手写的 config 与 Lightning LoRA 不兼容会导致 NaN
    # 如果默认配置报错，你再把下面这段注释取消回来
    
    # scheduler_config = {
    #     "base_image_seq_len": 256,
    #     "base_shift": math.log(3),
    #     "invert_sigmas": False,
    #     "max_image_seq_len": 8192,
    #     "max_shift": math.log(3),
    #     "num_train_timesteps": 1000,
    #     "shift": 1.0,
    #     "shift_terminal": None,
    #     "stochastic_sampling": False,
    #     "time_shift_type": "exponential",
    #     "use_beta_sigmas": False,
    #     "use_dynamic_shifting": True,
    #     "use_exponential_sigmas": False,
    #     "use_karras_sigmas": False,
    # }
    # scheduler = FlowMatchEulerDiscreteScheduler.from_config(scheduler_config)
    
    # 使用默认加载器 (更加稳妥)
    print("Loading default scheduler from model path...")
    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(args.model_path, subfolder="scheduler")

    if args.lora_path is not None:
        print(f"Loading with LoRA from: {args.lora_path}")
        
        pipe = pipe_cls.from_pretrained(
            args.model_path, 
            scheduler=scheduler, 
            torch_dtype=torch_dtype,  # 这里全是 float32
            device_map="balanced"
        )
        pipe.load_lora_weights(args.lora_path)
    else:
        pipe = pipe_cls.from_pretrained(
            args.model_path, 
            scheduler=scheduler,
            torch_dtype=torch_dtype, 
            device_map="balanced"
        )

    # ============================================================
    # 3. 诊断代码 (保留以防万一)
    # ============================================================
    # 既然已经是全 FP32，不需要 VAE Patch。
    # 但我们保留一个检测器，如果还黑屏，它会告诉我们。
    if hasattr(pipe, "vae"):
        # 禁用切片以保证计算一致性
        try:
            pipe.vae.disable_slicing()
            pipe.vae.disable_tiling()
        except:
            pass

        # Hook decode 仅仅为了打印日志
        if not hasattr(pipe.vae, "_original_decode"):
            pipe.vae._original_decode = pipe.vae.decode

        def debug_decode(z, *args, **kwargs):
            if torch.isnan(z).any() or torch.isinf(z).any():
                print("!!! Still NaN inside Transformer output !!!", flush=True)
            return pipe.vae._original_decode(z, *args, **kwargs)
        
        pipe.vae.decode = debug_decode

    pipe.set_progress_bar_config(disable=None)

    # 4. 数据准备
    input_images = []
    if args.image_paths:
        for img_path in args.image_paths:
            print(f"Loading image: {img_path}")
            input_images.append(Image.open(img_path).convert("RGB"))
    else:
        raise ValueError("Please provide input images using --image_paths")

    # 5. 参数配置
    if args.steps is None:
        num_inference_steps = 8 if args.lora_path else 50
    else:
        num_inference_steps = args.steps

    if args.cfg is None:
        true_cfg_scale = 1.0 if args.lora_path else 4.0
    else:
        true_cfg_scale = args.cfg

    generator = torch.Generator(device="cpu").manual_seed(args.seed)

    inputs = {
        "image": input_images,
        "prompt": args.prompt,
        "generator": generator,
        "true_cfg_scale": true_cfg_scale,
        "negative_prompt": args.negative_prompt,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": 1.0,
    }
    
    if not is_edit_plus and len(input_images) == 1:
        pass

    print(f"Start inference with prompt: '{args.prompt}'")
    
    # 6. 执行推理
    with torch.inference_mode():
        output = pipe(**inputs)
        output_image = output.images[0]

    # 7. 保存
    os.makedirs(args.out_dir, exist_ok=True)
    save_path = os.path.join(args.out_dir, args.output_filename)
    output_image.save(save_path)
    print(f"Image saved successfully at: {os.path.abspath(save_path)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qwen Image Edit Merged Script")
    
    # 模型路径 (本地)
    parser.add_argument("--model_path", type=str, required=True, help="Local path to the model folder (e.g., /data/models/Qwen-Image-Edit-2509)")
    parser.add_argument("--lora_path", type=str, default=None, help="Local path to LoRA weights (optional)")
    
    # 输入相关
    parser.add_argument("--image_paths", nargs='+', required=True, help="List of input image paths (e.g., input1.png input2.png)")
    parser.add_argument("--prompt", type=str, required=True, help="Editing prompt")
    parser.add_argument("--negative_prompt", type=str, default=" ", help="Negative prompt")
    
    # 输出相关
    parser.add_argument("--out_dir", type=str, default="results", help="Output directory")
    parser.add_argument("--output_filename", type=str, default="output_merged.png", help="Output filename")
    
    # 参数相关
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--steps", type=int, default=None, help="Inference steps (default: 40-50 for base, 8 for LoRA)")
    parser.add_argument("--cfg", type=float, default=None, help="True CFG scale (default: 4.0 for base, 1.0 for LoRA)")
    parser.add_argument("--force_plus", action="store_true", help="Force use QwenImageEditPlusPipeline if model name doesn't contain '2509'")

    args = parser.parse_args()
    
    # 校验 LoRA 路径
    if args.lora_path is not None and not os.path.exists(args.lora_path):
        raise FileNotFoundError(f"Lora path {args.lora_path} does not exist")

    main(args)