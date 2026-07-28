'''
5 step / 3 min
Mapping pos_embed to cuda:1
Mapping time_text_embed to cuda:1
Mapping txt_norm to cuda:1
Mapping img_in to cuda:1
Mapping txt_in to cuda:1
Mapping norm_out to cuda:1
Mapping proj_out to cuda:1
VAE + text_encoder -> GPU 0
Blocks 0-19 -> GPU 1
Blocks 20-39 -> GPU 2
Blocks 40-59 -> GPU 3
'''
import torch
import numpy as np
from diffusers import DiffusionPipeline
# from diffusers.pipelines.qwenimage import QwenImagePipeline, QwenImageEditPipeline
from diffusers import QwenImageEditPlusPipeline
from diffusers.pipelines.qwenimage.pipeline_output import QwenImagePipelineOutput
from typing import Any, Callable, Dict, List, Optional, Union
from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps
from diffusers.utils import is_torch_xla_available
from diffusers.utils.torch_utils import randn_tensor
from diffusers.image_processor import PipelineImageInput
from diffusers.pipelines.qwenimage.pipeline_qwenimage_edit_plus import calculate_shift, calculate_dimensions


PREFERRED_QWENIMAGE_RESOLUTIONS = [
    (672, 1568),
    (688, 1504),
    (720, 1456),
    (752, 1392),
    (800, 1328),
    (832, 1248),
    (880, 1184),
    (944, 1104),
    (1024, 1024),
    (1104, 944),
    (1184, 880),
    (1248, 832),
    (1328, 800),
    (1392, 752),
    (1456, 720),
    (1504, 688),
    (1568, 672),
]

if is_torch_xla_available():
    import torch_xla.core.xla_model as xm

    XLA_AVAILABLE = True
else:
    XLA_AVAILABLE = False

class MultiGPUTransformer:
    """multi GPU包装器,通过device_map自动分配"""
    
    def __init__(self, transformer, gpu_split_points=None):
        self.transformer = transformer
        self.config = transformer.config
        
        # 记录分割点信息（仅用于显示）
        total_blocks = len(transformer.transformer_blocks)
        if gpu_split_points is None:
            split_1 = total_blocks // 3
            split_2 = 2 * total_blocks // 3
            gpu_split_points = [split_1, split_2]
        
        self.gpu_split_points = gpu_split_points
        self.total_blocks = total_blocks
        self.setup_multi_gpu()
        
    def setup_multi_gpu(self):
        """设置多GPU分布 - 使用accelerate的device_map功能"""
        print("Setting up multi-GPU distribution using device_map...")
        
        # 创建device_map字典
        device_map = {}
        
        # 将非transformer_blocks组件放在cuda:1
        for name, module in self.transformer.named_children():
            if name != "transformer_blocks":
                device_map[name] = "cuda:1"
                print(f"Mapping {name} to cuda:1")
        
        # 分配transformer blocks
        for i in range(self.total_blocks):
            if i < self.gpu_split_points[0]:
                device_map[f"transformer_blocks.{i}"] = "cuda:1"
            elif i < self.gpu_split_points[1]:
                device_map[f"transformer_blocks.{i}"] = "cuda:2"
            else:
                device_map[f"transformer_blocks.{i}"] = "cuda:3"
        
        # 使用accelerate进行设备分配
        try:
            from accelerate import dispatch_model
            self.transformer = dispatch_model(self.transformer, device_map=device_map)
            print("Successfully applied device_map using accelerate")
        except ImportError:
            print("Accelerate not available, falling back to manual device placement")
            self._manual_device_placement()
        except Exception as e:
            print(f"Error with accelerate dispatch: {e}, falling back to manual placement")
            self._manual_device_placement()
            
        print(f"Blocks 0-{self.gpu_split_points[0]-1} -> GPU 1")
        print(f"Blocks {self.gpu_split_points[0]}-{self.gpu_split_points[1]-1} -> GPU 2") 
        print(f"Blocks {self.gpu_split_points[1]}-{self.total_blocks-1} -> GPU 3")
        
    def _manual_device_placement(self):
        """手动设备分配作为后备方案"""
        # 将transformer的非block组件放在GPU 1
        for name, module in self.transformer.named_children():
            if name != "transformer_blocks":
                module.to("cuda:1")
                print(f"Moved {name} to cuda:1")
        
        # 分配transformer blocks
        for i, block in enumerate(self.transformer.transformer_blocks):
            if i < self.gpu_split_points[0]:
                block.to("cuda:1")
            elif i < self.gpu_split_points[1]:
                block.to("cuda:2") 
            else:
                block.to("cuda:3")
        
    def cache_context(self, name):
        return self.transformer.cache_context(name)
        
    @property 
    def device(self):
        return torch.device("cuda:1")  # transformer的主设备是cuda:1
    
    @property
    def dtype(self):
        return self.transformer.dtype
        
    def __call__(self, *args, **kwargs):
        """直接使用原始transformer的forward方法"""
        return self.transformer(*args, **kwargs)

CONDITION_IMAGE_SIZE = 384 * 384
VAE_IMAGE_SIZE = 1024 * 1024


class MyQwenImageEditPipeline(QwenImageEditPlusPipeline):

    @torch.no_grad()
    def __call__(
        self,
        image: Optional[PipelineImageInput] = None,
        prompt: Union[str, List[str]] = None,
        negative_prompt: Union[str, List[str]] = None,
        true_cfg_scale: float = 4.0,
        height: Optional[int] = None,
        width: Optional[int] = None,
        num_inference_steps: int = 50,
        sigmas: Optional[List[float]] = None,
        guidance_scale: Optional[float] = None,
        num_images_per_prompt: int = 1,
        generator: Optional[Union[torch.Generator, List[torch.Generator]]] = None,
        latents: Optional[torch.Tensor] = None,
        prompt_embeds: Optional[torch.Tensor] = None,
        prompt_embeds_mask: Optional[torch.Tensor] = None,
        negative_prompt_embeds: Optional[torch.Tensor] = None,
        negative_prompt_embeds_mask: Optional[torch.Tensor] = None,
        output_type: Optional[str] = "pil",
        return_dict: bool = True,
        attention_kwargs: Optional[Dict[str, Any]] = None,
        callback_on_step_end: Optional[Callable[[int, int, Dict], None]] = None,
        callback_on_step_end_tensor_inputs: List[str] = ["latents"],
        max_sequence_length: int = 512,
    ):
        image_size = image[-1].size if isinstance(image, list) else image.size
        calculated_width, calculated_height = calculate_dimensions(1024 * 1024, image_size[0] / image_size[1])
        height = height or calculated_height
        width = width or calculated_width
        print(height, width)

        multiple_of = self.vae_scale_factor * 2
        width = width // multiple_of * multiple_of
        height = height // multiple_of * multiple_of

        # 1. Check inputs. Raise error if not correct
        self.check_inputs(
            prompt,
            height,
            width,
            negative_prompt=negative_prompt,
            prompt_embeds=prompt_embeds,
            negative_prompt_embeds=negative_prompt_embeds,
            prompt_embeds_mask=prompt_embeds_mask,
            negative_prompt_embeds_mask=negative_prompt_embeds_mask,
            callback_on_step_end_tensor_inputs=callback_on_step_end_tensor_inputs,
            max_sequence_length=max_sequence_length,
        )
        
        self._guidance_scale = guidance_scale
        self._attention_kwargs = attention_kwargs
        self._current_timestep = None
        self._interrupt = False

        # 2. Define call parameters
        if prompt is not None and isinstance(prompt, str):
            batch_size = 1
        elif prompt is not None and isinstance(prompt, list):
            batch_size = len(prompt)
        else:
            batch_size = prompt_embeds.shape[0]

        device = self._execution_device
        # VAE和text_encoder在cuda:0，使用cuda:0作为主设备
        device = torch.device("cuda:0")
        # 3. Preprocess image
        if image is not None and not (isinstance(image, torch.Tensor) and image.size(1) == self.latent_channels):
            if not isinstance(image, list):
                image = [image]
            condition_image_sizes = []
            condition_images = []
            vae_image_sizes = []
            vae_images = []
            for img in image:
                image_width, image_height = img.size
                condition_width, condition_height = calculate_dimensions(
                    CONDITION_IMAGE_SIZE, image_width / image_height
                )
                vae_width, vae_height = calculate_dimensions(VAE_IMAGE_SIZE, image_width / image_height)
                condition_image_sizes.append((condition_width, condition_height))
                vae_image_sizes.append((vae_width, vae_height))
                condition_images.append(self.image_processor.resize(img, condition_height, condition_width))
                vae_images.append(self.image_processor.preprocess(img, vae_height, vae_width).unsqueeze(2))

            # img = image[0] if isinstance(image, list) else image
            # image_height, image_width = self.image_processor.get_default_height_width(img)
            # aspect_ratio = image_width / image_height
            # if _auto_resize:
            #     _, image_width, image_height = min(
            #         (abs(aspect_ratio - w / h), w, h) for w, h in PREFERRED_QWENIMAGE_RESOLUTIONS
            #     )
            # image_width = image_width // multiple_of * multiple_of
            # image_height = image_height // multiple_of * multiple_of
            # image = self.image_processor.resize(image, image_height, image_width)
            # prompt_image = image
            # image = self.image_processor.preprocess(image, image_height, image_width)
            # image = image.unsqueeze(2)

        has_neg_prompt = negative_prompt is not None or (
            negative_prompt_embeds is not None and negative_prompt_embeds_mask is not None
        )

        do_true_cfg = true_cfg_scale > 1 and has_neg_prompt
        prompt_embeds, prompt_embeds_mask = self.encode_prompt(
            image=condition_images,
            prompt=prompt,
            prompt_embeds=prompt_embeds,
            prompt_embeds_mask=prompt_embeds_mask,
            device=device,
            num_images_per_prompt=num_images_per_prompt,
            max_sequence_length=max_sequence_length,
        )
        if do_true_cfg:
            # negative image is the same size as the original image, but all pixels are white
            # negative_image = Image.new("RGB", (image.width, image.height), (255, 255, 255))

            negative_prompt_embeds, negative_prompt_embeds_mask = self.encode_prompt(
                image=condition_images,
                prompt=negative_prompt,
                prompt_embeds=negative_prompt_embeds,
                prompt_embeds_mask=negative_prompt_embeds_mask,
                device=device,
                num_images_per_prompt=num_images_per_prompt,
                max_sequence_length=max_sequence_length,
            )

        # 4. Prepare latent variables
        vae_device = self.vae.device  # cuda:0
        transformer_device = self.transformer.device  # cuda:1
        # 将embeddings移到transformer设备
        prompt_embeds = prompt_embeds.to(transformer_device)
        prompt_embeds_mask = prompt_embeds_mask.to(transformer_device)

        if do_true_cfg:
            negative_prompt_embeds = negative_prompt_embeds.to(transformer_device)
            negative_prompt_embeds_mask = negative_prompt_embeds_mask.to(transformer_device)

        num_channels_latents = self.transformer.config.in_channels // 4
        latents, image_latents = self.prepare_latents(
            vae_images,
            batch_size * num_images_per_prompt,
            num_channels_latents,
            height,
            width,
            prompt_embeds.dtype,
            vae_device,
            generator,
            latents,
        )
        img_shapes = [
            [
                (1, height // self.vae_scale_factor // 2, width // self.vae_scale_factor // 2),
                *[
                    (1, vae_height // self.vae_scale_factor // 2, vae_width // self.vae_scale_factor // 2)
                    for vae_width, vae_height in vae_image_sizes
                ],
            ]
        ] * batch_size

        # 5. Prepare timesteps
        sigmas = np.linspace(1.0, 1 / num_inference_steps, num_inference_steps) if sigmas is None else sigmas
        image_seq_len = latents.shape[1]
        mu = calculate_shift(
            image_seq_len,
            self.scheduler.config.get("base_image_seq_len", 256),
            self.scheduler.config.get("max_image_seq_len", 4096),
            self.scheduler.config.get("base_shift", 0.5),
            self.scheduler.config.get("max_shift", 1.15),
        )
        timesteps, num_inference_steps = retrieve_timesteps(
            self.scheduler,
            num_inference_steps,
            device,
            sigmas=sigmas,
            mu=mu,
        )
        num_warmup_steps = max(len(timesteps) - num_inference_steps * self.scheduler.order, 0)
        self._num_timesteps = len(timesteps)

        # handle guidance
        if self.transformer.config.guidance_embeds and guidance_scale is None:
            raise ValueError("guidance_scale is required for guidance-distilled model.")
        elif self.transformer.config.guidance_embeds:
            guidance = torch.full([1], guidance_scale, device=device, dtype=torch.float32)
            guidance = guidance.expand(latents.shape[0])
        elif not self.transformer.config.guidance_embeds and guidance_scale is not None:
            print(
                f"guidance_scale is passed as {guidance_scale}, but ignored since the model is not guidance-distilled."
            )
            guidance = None
        elif not self.transformer.config.guidance_embeds and guidance_scale is None:
            guidance = None


        # # handle guidance
        # if self.transformer.config.guidance_embeds:
        #     guidance = torch.full([1], guidance_scale, device=device, dtype=torch.float32)
        #     guidance = guidance.expand(latents.shape[0])
        # else:
        #     guidance = None

        if self.attention_kwargs is None:
            self._attention_kwargs = {}

        txt_seq_lens = prompt_embeds_mask.sum(dim=1).tolist() if prompt_embeds_mask is not None else None
        negative_txt_seq_lens = (
            negative_prompt_embeds_mask.sum(dim=1).tolist() if negative_prompt_embeds_mask is not None else None
        )

        # 6. Denoising loop
        self.scheduler.set_begin_index(0)
        with self.progress_bar(total=num_inference_steps) as progress_bar:
            for i, t in enumerate(timesteps):
                if self.interrupt:
                    continue
                self._current_timestep = t

                # 将latents移到transformer设备
                latent_model_input = latents.to(transformer_device)
                if image_latents is not None:
                    latent_model_input = torch.cat([latents.to(transformer_device), image_latents.to(transformer_device)], dim=1)
                latent_model_input = latent_model_input.to(self.transformer.dtype)
                # broadcast to batch dimension in a way that's compatible with ONNX/Core ML
                timestep = t.expand(latents.shape[0]).to(self.transformer.dtype).to(transformer_device)
                prompt_embeds = prompt_embeds.to(self.transformer.dtype)
                # print(latent_model_input.dtype)
                # print(prompt_embeds.dtype)
                # print(self.transformer.transformer.dtype)
                with self.transformer.cache_context("cond"):
                    # 确保guidance在transformer设备上
                    if guidance is not None:
                        guidance = guidance.to(transformer_device)
                    
                    noise_pred = self.transformer(
                        hidden_states=latent_model_input,
                        timestep=timestep / 1000,
                        guidance=guidance,
                        encoder_hidden_states_mask=prompt_embeds_mask,
                        encoder_hidden_states=prompt_embeds,
                        img_shapes=img_shapes,
                        txt_seq_lens=txt_seq_lens,
                        attention_kwargs=self.attention_kwargs,
                        return_dict=False,
                    )[0]
                    noise_pred = noise_pred[:, : latents.size(1)]
                    noise_pred = noise_pred.to(vae_device)

                if do_true_cfg:
                    with self.transformer.cache_context("uncond"):
                        neg_noise_pred = self.transformer(
                            hidden_states=latent_model_input,
                            timestep=timestep / 1000,
                            guidance=guidance,
                            encoder_hidden_states_mask=negative_prompt_embeds_mask,
                            encoder_hidden_states=negative_prompt_embeds,
                            img_shapes=img_shapes,
                            txt_seq_lens=negative_txt_seq_lens,
                            attention_kwargs=self.attention_kwargs,
                            return_dict=False,
                        )[0]
                    neg_noise_pred = neg_noise_pred[:, : latents.size(1)]
                    
                    # 将neg_noise_pred移回VAE设备
                    neg_noise_pred = neg_noise_pred.to(vae_device)
                    comb_pred = neg_noise_pred + true_cfg_scale * (noise_pred - neg_noise_pred)

                    cond_norm = torch.norm(noise_pred, dim=-1, keepdim=True)
                    noise_norm = torch.norm(comb_pred, dim=-1, keepdim=True)
                    noise_pred = comb_pred * (cond_norm / noise_norm)

                # compute the previous noisy sample x_t -> x_t-1
                latents_dtype = latents.dtype
                latents = self.scheduler.step(noise_pred, t, latents, return_dict=False)[0]

                if latents.dtype != latents_dtype:
                    if torch.backends.mps.is_available():
                        # some platforms (eg. apple mps) misbehave due to a pytorch bug: https://github.com/pytorch/pytorch/pull/99272
                        latents = latents.to(latents_dtype)

                if callback_on_step_end is not None:
                    callback_kwargs = {}
                    for k in callback_on_step_end_tensor_inputs:
                        callback_kwargs[k] = locals()[k]
                    callback_outputs = callback_on_step_end(self, i, t, callback_kwargs)

                    latents = callback_outputs.pop("latents", latents)
                    prompt_embeds = callback_outputs.pop("prompt_embeds", prompt_embeds)

                # call the callback, if provided
                if i == len(timesteps) - 1 or ((i + 1) > num_warmup_steps and (i + 1) % self.scheduler.order == 0):
                    progress_bar.update()

                if XLA_AVAILABLE:
                    xm.mark_step()

        self._current_timestep = None
        if output_type == "latent":
            image = latents
        else:
            latents = self._unpack_latents(latents, height, width, self.vae_scale_factor)
            latents = latents.to(self.vae.dtype)
            latents_mean = (
                torch.tensor(self.vae.config.latents_mean)
                .view(1, self.vae.config.z_dim, 1, 1, 1)
                .to(latents.device, latents.dtype)
            )
            latents_std = 1.0 / torch.tensor(self.vae.config.latents_std).view(1, self.vae.config.z_dim, 1, 1, 1).to(
                latents.device, latents.dtype
            )
            latents = latents / latents_std + latents_mean
            image = self.vae.decode(latents, return_dict=False)[0][:, :, 0]
            image = self.image_processor.postprocess(image, output_type=output_type)

        # Offload all models
        self.maybe_free_model_hooks()

        if not return_dict:
            return (image,)

        return QwenImagePipelineOutput(images=image)


if __name__ == "__main__":
    from PIL import Image
    # from prompt_utils import polish_edit_prompt
    pipeline = MyQwenImageEditPipeline.from_pretrained(
        "/storage/v-xiangxizheng/cache/Qwen-Image-Edit-2509",
        torch_dtype=torch.bfloat16
    )
    # pipeline.to(torch.bfloat16)
    # pipeline.text_encoder.to(torch.bfloat16)
    pipeline.transformer.to(torch.float32)
    # 设置VAE和text_encoder到GPU 0
    pipeline.vae.to("cuda:0")
    pipeline.text_encoder.to("cuda:0")
    
    # 使用多GPU包装器替换原始的transformer
    # 自定义分割点
    total_blocks = len(pipeline.transformer.transformer_blocks)
    print(f"Total transformer blocks: {total_blocks}")
    
    gpu_split_points = [total_blocks//3, 2*total_blocks//3]  # 三等分
    pipeline.transformer = MultiGPUTransformer(pipeline.transformer, gpu_split_points)
    
    print(f"GPU split points: {gpu_split_points}")
    print(f"GPU 0: VAE + text_encoder")
    print(f"GPU 1: transformer non-block components + blocks 0-{gpu_split_points[0]-1}")
    print(f"GPU 2: blocks {gpu_split_points[0]}-{gpu_split_points[1]-1}")
    print(f"GPU 3: blocks {gpu_split_points[1]}-{total_blocks-1}")
    

    pipeline.set_progress_bar_config(disable=None)

    # image = Image.open("../textbox_data/textimage_demo.jpg").convert("RGB")
    # prompt = "Edit the image according to the text in the image, and finally delete the text in the image."
    # prompt = polish_edit_prompt(prompt, image)

    import argparse

    parser = argparse.ArgumentParser(description="Process some images.")
    parser.add_argument("--image", type=str, default="/root/molmoact/00000000.png", help="Path to the input image.")
    parser.add_argument("--prompt", type=str, default="remove the pillow on the right side.", help="Text prompt for the model.")
    parser.add_argument("--output_path", type=str, default="output.png", help="Path to the output image.")
    parser.add_argument("--num_inference_steps", type=int, default=20, help="Number of inference steps.")
    args = parser.parse_args()

    image = Image.open(args.image).convert("RGB")
    prompt = args.prompt

    # image = Image.open("/root/molmoact/00000000.png").convert("RGB")
    # prompt = "remove the pillow on the right side."
    generator = torch.Generator(device="cuda").manual_seed(0)
    input_width, input_height = image.size
    inputs = {
        "image": image,
        "prompt": prompt,
        "generator": generator,
        "true_cfg_scale": 4.0,
        "negative_prompt": " ",
        "num_inference_steps": args.num_inference_steps,
        "guidance_scale": 1.0,
        # "width" : input_width,
        # "height" : input_height,
    }

    with torch.inference_mode():
        output = pipeline(**inputs)
        output_image = output.images[0]
        output_image.save(args.output_path)
        print(args.output_path)

'''
CUDA_VISIBLE_DEVICES=0,1,2,3 \
python qwen-infer-plus.py \
--image /root/molmoact/00000000.png \
--prompt "Replace the checkered pillow on the right side of the sofa with a plush toy resembling a gray and white cat, sitting upright with soft texture and visible ears, positioned in the same location." \
--output_path /root/molmoact/output/step5.png --num_inference_steps 5

CUDA_VISIBLE_DEVICES=4,5,6,7 \
python qwen-infer-plus.py \
--image /root/molmoact/00000000.png \
--prompt "Replace the checkered pillow on the right side of the sofa with a plush toy resembling a gray and white cat, sitting upright with soft texture and visible ears, positioned in the same location." \
--output_path /root/molmoact/output/step10.png --num_inference_steps 10
'''