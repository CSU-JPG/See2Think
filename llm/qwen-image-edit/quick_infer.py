import torch
from accelerate import dispatch_model
from vanillaPipeline import VanillaPipeline
from PIL import Image
import math
import argparse
from peft import PeftModel, LoraConfig
from safetensors.torch import load_file
from wrapped_tools import MultiGPUTransformer, doubleStringTransformer
from diffusers import FlowMatchEulerDiscreteScheduler

# > tools -----------------------------------------------------------------------------

# args parser
def parse_args():
    parser = argparse.ArgumentParser(description="Train LoRA for Qwen Image Edit (Accelerate+DeepSpeed)")

    # Paths / Basics
    parser.add_argument("--output_img", type=str, default="qwen_test.png")
    parser.add_argument("--pretrained_model", type=str, default="qwen_image_edit")

    # LoRA / Quant
    parser.add_argument("--lora_weight", type=str, default="checkpoint-1/")

    # inputs
    parser.add_argument("--ctrl_img", type=str, default="input.png")
    parser.add_argument("--rank", type=int, default=64, help="Rank for LoRA.")
    parser.add_argument("--prompt", type=str, default="follow the words instruction to edit image")
    parser.add_argument("--neg_prompt", type=str, default="bounding box, red rectangle, text, words, letters, characters, labels, annotations, arrows, markers, highlights, sketches, borders, frames, outlines, watermarks, logos, signatures, captions, instructions, notes, diagrams, symbols, non-photorealistic elements, artifacts, residual traces, incomplete erasure, partial removal")

    # infer arguments
    parser.add_argument("--target_area", type=int, default=512*512, help="Approximate target area (H*W) for 32-aligned resize")
    parser.add_argument("--infer_steps", type=int, default=50)
    parser.add_argument("--cfg_scale", type=float, default=6.0, help="Classifier-Free Guidance scale.")

    # seed
    parser.add_argument("--seed", type=int, default=42, help="A seed for reproducible training.")

    return parser.parse_args()

# load image
def get_image(path):
    img = Image.open(path).convert("RGB")
    pass

    return img

# calculate dimension for easy divised by 32
def calculate_dimensions(target_area, ratio):
    width = math.sqrt(target_area * ratio)
    height = width / ratio

    width = round(width / 32) * 32
    height = round(height / 32) * 32

    return width, height

    
# > main -----------------------------------------------------------------------------

def main():
    args = parse_args()
    dtype = torch.bfloat16

    print(f"Loading base model: {args.pretrained_model}")
    pipe = VanillaPipeline.from_pretrained(args.pretrained_model,
                                                    torch_dtype=dtype).to("cpu")

    #  Scheduler 配置
    print("Applying Lightning Scheduler Config...")
    scheduler_config = {
        "base_image_seq_len": 256,
        "base_shift": math.log(3),  # 关键：Shift = 3
        "invert_sigmas": False,
        "max_image_seq_len": 8192,
        "max_shift": math.log(3),   # 关键：Shift = 3
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

    # 替换 pipe 中的 scheduler
    # 注意：我们要确保 scheduler 和 pipe 在同一个 dtype/device 逻辑下兼容
    # 通常 scheduler 不占显存，可以直接替换
    pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(scheduler_config)
    # ================= 核心修改结束 =================

    pipe.vae.to("cuda:0")
    pipe.text_encoder.to("cuda:0")


    # ==================== 核心修改：手动强力加载 LoRA ====================
    if args.lora_weight:
        print(f"Loading Lightning LoRA from: {args.lora_weight}")
        
        # 1. 定义 Config (直接写死，防止读取 json 失败)
        # 这些是自动生成的 target_modules
        target_modules = ['to_v', 'to_q', 'add_k_proj', 'proj', 'add_v_proj', 'add_q_proj', 'to_k', 'to_add_out']
        peft_config = LoraConfig(
            r=64,
            lora_alpha=16,
            target_modules=target_modules,
            lora_dropout=0.05,
            bias="none",
            task_type=None
        )

        # 2. 初始化 PeftModel 结构 (此时权重是随机的)
        # pipe.transformer 变成了 PeftModel
        pipe.transformer = PeftModel(pipe.transformer, peft_config)

        # 3. 手动读取 .safetensors 文件
        import os
        safetensors_path = os.path.join(args.lora_weight, "adapter_model.safetensors")
        # 如果找不到，尝试找 fixed 版本
        if not os.path.exists(safetensors_path):
             safetensors_path = os.path.join(args.lora_weight, "adapter_model_fixed.safetensors")
        
        print(f"Reading weights from {safetensors_path}...")
        state_dict = load_file(safetensors_path)

       # 4. 内存中重命名 + 前缀修复
        new_state_dict = {}
        for key, val in state_dict.items():
            new_key = key
            
            # --- 核心修复：必须加上 .default 后缀 ---
            # 原始: transformer_blocks...lora_down.weight
            # 目标: base_model.model.transformer_blocks...lora_A.default.weight
            
            if "lora_down" in new_key:
                new_key = new_key.replace("lora_down", "lora_A.default")
            elif "lora_up" in new_key:
                new_key = new_key.replace("lora_up", "lora_B.default")
            
            # 处理 alpha (如果有的话，通常叫 alpha.default)
            elif "alpha" in new_key:
                # 尝试匹配: transformer_blocks.0...alpha -> base_model.model...lora_alpha.default
                new_key = new_key.replace("alpha", "lora_alpha.default")
            
            # 修复前缀: PeftModel 内部通常需要 base_model.model 前缀
            if not new_key.startswith("base_model.model."):
                new_key = "base_model.model." + new_key
                
            new_state_dict[new_key] = val

        # 5. 强行加载 (strict=False 忽略 alpha 权重或其他不匹配的权重)
        print("Injecting weights into model...")
        incompatible = pipe.transformer.load_state_dict(new_state_dict, strict=False)
        
        # 打印调试信息：只要 missing_keys 里没有 lora_A/lora_B 就是成功的
        missing_lora = [k for k in incompatible.missing_keys if "lora_" in k]
        if len(missing_lora) > 0:
            print(f"⚠️ 警告: 仍有部分 LoRA 权重未加载: {missing_lora[:5]}...")
        else:
            print("✅ LoRA 权重完美加载！(忽略关于 base model keys 的 missing 警告)")

        # 6. 合并并卸载 (变回普通 Transformer 以支持多卡)
        print("Merging LoRA weights...")
        pipe.transformer = pipe.transformer.merge_and_unload()
    
    # ====================================================================

    # --- 此时 pipe.transformer 已经是一个融合了 Lightning 权重的普通模型 ---

    flux_transformer = MultiGPUTransformer(pipe.transformer).auto_split()
    # if args.lora_weight:
    #     print(f"Loading LoRA weights from: {args.lora_weight}")
    #     def _unwrap(m):
    #                     return m._orig_mod if hasattr(m, "_orig_mod") else m
    #     _unwrap_flux = _unwrap(flux_transformer)
    #     flux_transformer = PeftModel.from_pretrained(_unwrap_flux, args.lora_weight, low_cpu_mem_usage=False)
    flux_transformer.eval()
    pipe.transformer = flux_transformer


    generator = torch.Generator(device="cuda").manual_seed(args.seed)

    image = get_image(args.ctrl_img)

    inputs = {
        "image": image,
        "prompt": args.prompt,
        "generator": generator,
        "true_cfg_scale": args.cfg_scale,
        "negative_prompt": args.neg_prompt,
        "num_inference_steps": args.infer_steps,
        "target_area":args.target_area,
        "max_sequence_length":1024
    }

    pipe.set_progress_bar_config(disable=None)

    with torch.inference_mode():
        output = pipe(**inputs)
        output_image = output.images[0]
        output_image.save(args.output_img)
    print(f"Image successfully saved to {args.output_img}")

if __name__ == "__main__":
    main()    

