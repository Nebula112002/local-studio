from __future__ import annotations

import asyncio
import base64
import json
import random
import uuid
from typing import Any

import httpx
import websockets

from server.progress import progress_state

from .base import BackendInfo, BaseBackend, GenerationParams, GenerationResult

_VIDEO_NAME_TOKENS = ("svd", "wan", "ti2v", "i2v", "t2v", "ltx", "hunyuan", "video2")
_VIDEO_FILE_SUFFIXES = (".mp4", ".webm", ".mkv", ".gif", ".mov")


class ComfyUIBackend(BaseBackend):
    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)
        self._object_info: dict[str, Any] | None = None

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/system_stats")
                return response.status_code == 200
        except Exception:
            return False

    async def _fetch_object_info(self) -> dict[str, Any]:
        if self._object_info is not None:
            return self._object_info
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/object_info")
            response.raise_for_status()
            self._object_info = response.json()
            return self._object_info

    def _list_from_object_info(self, info: dict[str, Any], node: str, field: str) -> list[str]:
        node_info = info.get(node, {}).get("input", {}).get("required", {})
        values = node_info.get(field, [[]])[0]
        return values if isinstance(values, list) else []

    @staticmethod
    def _is_video_checkpoint_name(name: str) -> bool:
        lowered = name.lower().replace("\\", "/")
        return any(token in lowered for token in _VIDEO_NAME_TOKENS)

    @staticmethod
    def _is_wan_name(name: str | None) -> bool:
        return bool(name) and "wan" in name.lower()

    @staticmethod
    def _is_svd_name(name: str | None) -> bool:
        return bool(name) and "svd" in name.lower()

    @staticmethod
    def _wan_family(name: str | None) -> str:
        lowered = (name or "").lower()
        if "5b" in lowered or "ti2v" in lowered:
            return "ti2v_5b"
        if "i2v" in lowered:
            return "i2v"
        return "t2v"

    def _unet_names(self, info: dict[str, Any]) -> list[str]:
        return self._list_from_object_info(info, "UNETLoader", "unet_name")

    def _lora_names(self, info: dict[str, Any]) -> list[str]:
        names = self._list_from_object_info(info, "LoraLoaderModelOnly", "lora_name")
        if names:
            return names
        return self._list_from_object_info(info, "LoraLoader", "lora_name")

    def _clip_names(self, info: dict[str, Any]) -> list[str]:
        return self._list_from_object_info(info, "CLIPLoader", "clip_name")

    def _vae_names(self, info: dict[str, Any]) -> list[str]:
        return self._list_from_object_info(info, "VAELoader", "vae_name")

    def _svd_checkpoints(self, info: dict[str, Any]) -> list[str]:
        return [
            name
            for name in self._list_from_object_info(info, "ImageOnlyCheckpointLoader", "ckpt_name")
            if self._is_svd_name(name)
        ]

    def _wan_unets(self, info: dict[str, Any]) -> list[str]:
        return [name for name in self._unet_names(info) if self._is_wan_name(name)]

    def _list_video_models(self, info: dict[str, Any]) -> list[str]:
        models: list[str] = []
        for name in self._wan_unets(info):
            if name not in models:
                models.append(name)
        for name in self._svd_checkpoints(info):
            if name not in models:
                models.append(name)
        return models

    def _has_wan_pipeline(self, info: dict[str, Any]) -> bool:
        if not self._wan_unets(info):
            return False
        return "EmptyHunyuanLatentVideo" in info or "Wan22ImageToVideoLatent" in info or "WanImageToVideo" in info

    def _has_svd_pipeline(self, info: dict[str, Any]) -> bool:
        return "SVD_img2vid_Conditioning" in info and bool(self._svd_checkpoints(info))

    async def get_info(self) -> BackendInfo:
        info = await self._fetch_object_info()
        models = [
            model
            for model in self._list_from_object_info(info, "CheckpointLoaderSimple", "ckpt_name")
            if not self._is_video_checkpoint_name(model)
        ]
        samplers = self._list_from_object_info(info, "KSampler", "sampler_name")
        schedulers = self._list_from_object_info(info, "KSampler", "scheduler")
        if not schedulers:
            schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        video_models = self._list_video_models(info)

        capabilities = ["txt2img", "img2img"]
        if self._has_wan_pipeline(info) or self._has_svd_pipeline(info):
            capabilities.extend(["img2video", "txt2video"])

        return BackendInfo(
            name="ComfyUI",
            backend_type="comfyui",
            url=self.base_url,
            models=models,
            samplers=samplers,
            schedulers=schedulers,
            video_models=video_models,
            capabilities=capabilities,
        )

    async def generate(self, params: GenerationParams) -> GenerationResult:
        info = await self.get_info()

        if params.mode == "txt2img":
            return await self._run_workflow(self._build_txt2img_workflow(params), params)
        if params.mode == "img2img":
            if not params.init_image:
                raise ValueError("Image-to-image requires a source image.")
            uploaded = await self._upload_image(params.init_image)
            return await self._run_workflow(self._build_img2img_workflow(params, uploaded), params)
        if params.mode in ("img2video", "txt2video"):
            return await self._generate_video(params, info)

        raise ValueError(f"Unsupported mode: {params.mode}")

    async def _generate_video(self, params: GenerationParams, info: BackendInfo) -> GenerationResult:
        object_info = await self._fetch_object_info()
        use_wan = self._should_use_wan(params, object_info)
        if params.mode == "img2video" and not params.init_image:
            raise ValueError("Image-to-video requires a source image.")
        if use_wan:
            if not self._has_wan_pipeline(object_info):
                raise RuntimeError(self._video_setup_error())
            if params.mode == "txt2video":
                return await self._run_workflow(self._build_wan_workflow(params), params, expect_video=True)
            uploaded = await self._upload_image(params.init_image or "")
            return await self._run_workflow(
                self._build_wan_workflow(params, uploaded),
                params,
                expect_video=True,
            )
        if not self._has_svd_pipeline(object_info):
            raise RuntimeError(self._video_setup_error())
        if params.mode == "img2video":
            uploaded = await self._upload_image(params.init_image or "")
            return await self._run_workflow(self._build_svd_workflow(params, uploaded), params, expect_video=True)
        still = await self._run_workflow(self._build_txt2img_workflow(params), params)
        if not still.images:
            raise RuntimeError("Failed to generate starting frame for video.")
        uploaded = await self._upload_image_ref(still.images[0])
        video = await self._run_workflow(self._build_svd_workflow(params, uploaded), params, expect_video=True)
        video.images = still.images[:1]
        video.metadata["start_frame_seed"] = still.seeds[0] if still.seeds else params.seed
        return video

    def _should_use_wan(self, params: GenerationParams, object_info: dict[str, Any]) -> bool:
        if self._is_svd_name(params.video_model) and self._has_svd_pipeline(object_info):
            return False
        if self._has_wan_pipeline(object_info):
            return True
        return False

    def _video_setup_error(self) -> str:
        return (
            "Video generation needs a Wan 2.2 or SVD video model in ComfyUI. "
            "This PC has Wan 2.2 T2V UNET files under diffusion_models — Local Studio will use those "
            "when ComfyUI can see them. SVD checkpoints (svd_xt) are optional."
        )

    @staticmethod
    def _resolve_seed(params: GenerationParams) -> int:
        return params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)

    @staticmethod
    def _sampler_seed(workflow: dict[str, Any]) -> int:
        for node in workflow.values():
            inputs = node.get("inputs", {})
            class_type = node.get("class_type")
            if class_type == "KSampler" and "seed" in inputs:
                return int(inputs["seed"])
            if class_type == "KSamplerAdvanced" and "noise_seed" in inputs:
                return int(inputs["noise_seed"])
        return 0

    @staticmethod
    def _apply_clip_skip(
        workflow: dict[str, Any],
        params: GenerationParams,
        checkpoint_node: str = "4",
        encode_nodes: tuple[str, ...] = ("6", "7"),
        skip_node: str = "12",
    ) -> None:
        skip = int(params.clip_skip or 1)
        if skip <= 1:
            return
        workflow[skip_node] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "clip": [checkpoint_node, 1],
                "stop_at_clip_layer": -skip,
            },
        }
        for node_id in encode_nodes:
            if node_id in workflow:
                workflow[node_id]["inputs"]["clip"] = [skip_node, 0]

    def _build_txt2img_workflow(self, params: GenerationParams) -> dict[str, Any]:
        seed = self._resolve_seed(params)
        model = params.model or self._default_checkpoint()
        workflow: dict[str, Any] = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": params.steps,
                    "cfg": params.cfg_scale,
                    "sampler_name": params.sampler or "euler",
                    "scheduler": params.scheduler or "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": params.width, "height": params.height, "batch_size": params.batch_size},
            },
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": params.prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": params.negative_prompt, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "local_studio", "images": ["8", 0]}},
        }
        self._apply_clip_skip(workflow, params)
        return workflow

    def _build_img2img_workflow(self, params: GenerationParams, image_name: str) -> dict[str, Any]:
        seed = self._resolve_seed(params)
        model = params.model or self._default_checkpoint()
        workflow: dict[str, Any] = {
            "10": {"class_type": "LoadImage", "inputs": {"image": image_name}},
            "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["4", 2]}},
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": params.steps,
                    "cfg": params.cfg_scale,
                    "sampler_name": params.sampler or "euler",
                    "scheduler": params.scheduler or "normal",
                    "denoise": params.denoise,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["11", 0],
                },
            },
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": params.prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": params.negative_prompt, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "local_studio", "images": ["8", 0]}},
        }
        self._apply_clip_skip(workflow, params)
        return workflow

    def _build_svd_workflow(self, params: GenerationParams, image_name: str) -> dict[str, Any]:
        seed = self._resolve_seed(params)
        video_model = params.video_model or self._default_svd_model()
        if not self._is_svd_name(video_model):
            video_model = self._default_svd_model()
        # SVD works best at 1024x576; scale user request proportionally
        width = min(max(params.width, 256), 1024)
        height = min(max(params.height, 256), 576)
        if width / height > 1024 / 576:
            width = 1024
            height = 576
        else:
            height = min(height, 576)
            width = int(height * 1024 / 576)

        workflow: dict[str, Any] = {
            "1": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": video_model}},
            "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
            "3": {
                "class_type": "SVD_img2vid_Conditioning",
                "inputs": {
                    "clip_vision": ["1", 1],
                    "init_image": ["2", 0],
                    "vae": ["1", 2],
                    "width": width,
                    "height": height,
                    "video_frames": params.frames,
                    "motion_bucket_id": params.motion_bucket_id,
                    "fps": params.fps,
                    "augmentation_level": 0.0,
                },
            },
            "4": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": max(params.steps, 14),
                    "cfg": min(params.cfg_scale, 4.0) if params.cfg_scale > 4 else params.cfg_scale,
                    "sampler_name": params.sampler if params.sampler in ("euler", "euler_ancestral") else "euler",
                    "scheduler": params.scheduler if params.scheduler in ("karras", "normal", "simple") else "karras",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["3", 1],
                    "latent_image": ["3", 2],
                },
            },
            "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        }
        self._attach_video_output(workflow, params.fps, image_node="5")
        return workflow

    def _build_wan_workflow(self, params: GenerationParams, image_name: str | None = None) -> dict[str, Any]:
        seed = self._resolve_seed(params)
        bundle = self._resolve_wan_bundle(params)
        width, height = self._wan_dimensions(params, bundle["family"])
        length = self._wan_length(params.frames, bundle["family"])
        fps = self._wan_fps(params.fps)
        steps, cfg, sampler, scheduler, _lightning = self._wan_sampler_settings(params, bundle)

        high_model_node = "11"
        low_model_node = "12"
        clip_node = "13"
        vae_node = "14"
        pos_node = "15"
        neg_node = "16"
        latent_node = "20"

        workflow: dict[str, Any] = {
            "10": {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": bundle["high_unet"], "weight_dtype": "default"},
            },
            clip_node: {
                "class_type": "CLIPLoader",
                "inputs": {"clip_name": bundle["clip"], "type": "wan", "device": "default"},
            },
            vae_node: {"class_type": "VAELoader", "inputs": {"vae_name": bundle["vae"]}},
            pos_node: {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": params.prompt, "clip": [clip_node, 0]},
            },
            neg_node: {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": params.negative_prompt, "clip": [clip_node, 0]},
            },
        }

        shift = self._wan_shift(params.motion_bucket_id)
        high_src = "10"
        if bundle["high_lora"]:
            workflow["11a"] = {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": ["10", 0],
                    "lora_name": bundle["high_lora"],
                    "strength_model": 1.0,
                },
            }
            high_src = "11a"
        workflow[high_model_node] = {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": [high_src, 0], "shift": shift},
        }

        if bundle["low_unet"]:
            workflow["10b"] = {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": bundle["low_unet"], "weight_dtype": "default"},
            }
            low_src = "10b"
            if bundle["low_lora"]:
                workflow["12a"] = {
                    "class_type": "LoraLoaderModelOnly",
                    "inputs": {
                        "model": ["10b", 0],
                        "lora_name": bundle["low_lora"],
                        "strength_model": 1.0,
                    },
                }
                low_src = "12a"
            workflow[low_model_node] = {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": [low_src, 0], "shift": shift},
            }

        positive, negative, latent = self._attach_wan_latent(
            workflow,
            bundle["family"],
            image_name,
            width,
            height,
            length,
            pos_node,
            neg_node,
            vae_node,
            latent_node,
        )

        split_at = max(1, steps // 2)
        if bundle["low_unet"]:
            workflow["21"] = {
                "class_type": "KSamplerAdvanced",
                "inputs": {
                    "model": [high_model_node, 0],
                    "add_noise": "enable",
                    "noise_seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "positive": positive,
                    "negative": negative,
                    "latent_image": latent,
                    "start_at_step": 0,
                    "end_at_step": split_at,
                    "return_with_leftover_noise": "enable",
                },
            }
            workflow["22"] = {
                "class_type": "KSamplerAdvanced",
                "inputs": {
                    "model": [low_model_node, 0],
                    "add_noise": "disable",
                    "noise_seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "positive": positive,
                    "negative": negative,
                    "latent_image": ["21", 0],
                    "start_at_step": split_at,
                    "end_at_step": steps,
                    "return_with_leftover_noise": "disable",
                },
            }
            decode_from = "22"
        else:
            workflow["21"] = {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": [high_model_node, 0],
                    "positive": positive,
                    "negative": negative,
                    "latent_image": latent,
                },
            }
            decode_from = "21"

        workflow["30"] = {
            "class_type": "VAEDecode",
            "inputs": {"samples": [decode_from, 0], "vae": [vae_node, 0]},
        }
        self._attach_video_output(workflow, fps, image_node="30")
        return workflow

    def _attach_wan_latent(
        self,
        workflow: dict[str, Any],
        family: str,
        image_name: str | None,
        width: int,
        height: int,
        length: int,
        pos_node: str,
        neg_node: str,
        vae_node: str,
        latent_node: str,
    ) -> tuple[list[Any], list[Any], list[Any]]:
        info = self._object_info or {}
        use_22 = family == "ti2v_5b" and "Wan22ImageToVideoLatent" in info
        if use_22:
            inputs: dict[str, Any] = {
                "vae": [vae_node, 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
            }
            if image_name:
                workflow["18"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
                inputs["start_image"] = ["18", 0]
            workflow[latent_node] = {"class_type": "Wan22ImageToVideoLatent", "inputs": inputs}
            return [pos_node, 0], [neg_node, 0], [latent_node, 0]

        if image_name:
            workflow["18"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
            i2v_inputs: dict[str, Any] = {
                "positive": [pos_node, 0],
                "negative": [neg_node, 0],
                "vae": [vae_node, 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
                "start_image": ["18", 0],
            }
            clip_names = self._list_from_object_info(info, "CLIPVisionLoader", "clip_name")
            if clip_names and "CLIPVisionEncode" in info:
                clip_file = self._pick_name(clip_names, "clip_vision_h", "clip_vision") or clip_names[0]
                workflow["17"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": clip_file}}
                workflow["17b"] = {
                    "class_type": "CLIPVisionEncode",
                    "inputs": {"clip_vision": ["17", 0], "image": ["18", 0], "crop": "center"},
                }
                i2v_inputs["clip_vision_output"] = ["17b", 0]
            workflow[latent_node] = {"class_type": "WanImageToVideo", "inputs": i2v_inputs}
            return [latent_node, 0], [latent_node, 1], [latent_node, 2]

        workflow[latent_node] = {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {"width": width, "height": height, "length": length, "batch_size": 1},
        }
        return [pos_node, 0], [neg_node, 0], [latent_node, 0]

    def _attach_video_output(self, workflow: dict[str, Any], fps: int, image_node: str) -> None:
        output_id = str(max(int(node_id) for node_id in workflow if node_id.isdigit()) + 1)
        save_id = str(int(output_id) + 1)
        if self._object_info and "CreateVideo" in self._object_info:
            workflow[output_id] = {
                "class_type": "CreateVideo",
                "inputs": {"images": [image_node, 0], "fps": max(int(fps), 1)},
            }
            workflow[save_id] = {
                "class_type": "SaveVideo",
                "inputs": {
                    "filename_prefix": "local_studio",
                    "video": [output_id, 0],
                    "format": "auto",
                    "codec": "auto",
                },
            }
        elif self._object_info and "VHS_VideoCombine" in self._object_info:
            workflow[output_id] = {
                "class_type": "VHS_VideoCombine",
                "inputs": {
                    "images": [image_node, 0],
                    "frame_rate": max(int(fps), 1),
                    "loop_count": 0,
                    "filename_prefix": "local_studio",
                    "format": "video/h264-mp4",
                    "pingpong": False,
                    "save_output": True,
                },
            }
        else:
            workflow[output_id] = {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "local_studio_frames", "images": [image_node, 0]},
            }

    def _resolve_wan_bundle(self, params: GenerationParams) -> dict[str, Any]:
        info = self._object_info or {}
        unets = self._wan_unets(info)
        if not unets:
            raise RuntimeError(self._video_setup_error())
        loras = self._lora_names(info)
        clips = self._clip_names(info)
        vaes = self._vae_names(info)
        i2v = params.mode == "img2video"
        preferred = params.video_model if self._is_wan_name(params.video_model) else None

        high = self._pick_name(
            unets,
            "5b",
            "ti2v",
            *(["i2v", "high"] if i2v else ["t2v", "high"]),
            "wan",
        ) or unets[0]
        if preferred:
            if "low" in preferred.lower() and "high" not in preferred.lower():
                partner = self._matching_pair(preferred, unets, "high_noise", "high")
                high = partner or preferred
                low_override = preferred if partner else None
            else:
                high = preferred
                low_override = None
        else:
            low_override = None
        low = low_override or self._matching_pair(high, unets, "low_noise", "low")
        if low == high:
            low = None

        high_lora = self._matching_pair(high, loras, "lightx2v", "high")
        low_lora = self._matching_pair(low or high, loras, "lightx2v", "low") if low else None
        if high_lora and "low" in high_lora.lower() and "high" not in high_lora.lower():
            high_lora = self._pick_name(loras, "lightx2v", "high") or high_lora

        clip = self._pick_name(clips, "umt5") or (clips[0] if clips else None)
        family = self._wan_family(high)
        if family == "ti2v_5b":
            vae = self._pick_name(vaes, "wan2.2_vae", "wan2.2", "wan_2.1_vae", "wan") or (vaes[0] if vaes else None)
        else:
            vae = self._pick_name(vaes, "wan_2.1_vae", "wan2.1", "wan2.2_vae", "wan") or (vaes[0] if vaes else None)
        if not clip or not vae:
            raise RuntimeError(
                "Wan 2.2 video needs UMT5 CLIP and a Wan VAE in ComfyUI. "
                "Expected umt5_xxl plus wan_2.1_vae or wan2.2_vae."
            )
        return {
            "high_unet": high,
            "low_unet": low,
            "high_lora": high_lora,
            "low_lora": low_lora,
            "clip": clip,
            "vae": vae,
            "lightning": bool(high_lora or low_lora),
            "family": family,
        }

    @staticmethod
    def _pick_name(names: list[str], *needles: str) -> str | None:
        if not names:
            return None
        lowered = [(name, name.lower().replace("\\", "/")) for name in names]
        if not needles:
            return names[0]
        scored: list[tuple[int, str]] = []
        for name, low in lowered:
            score = 0
            for index, needle in enumerate(needles):
                if needle in low:
                    score += (len(needles) - index) * 10
            if score:
                scored.append((score, name))
        if scored:
            scored.sort(key=lambda item: (-item[0], item[1]))
            return scored[0][1]
        return None

    @staticmethod
    def _matching_pair(anchor: str | None, names: list[str], *needles: str) -> str | None:
        if not names:
            return None
        family = ""
        if anchor:
            low = anchor.lower()
            for token in ("i2v", "t2v", "ti2v"):
                if token in low:
                    family = token
                    break
        candidates = names
        if family:
            family_hits = [name for name in names if family in name.lower()]
            if family_hits:
                candidates = family_hits
        picked = ComfyUIBackend._pick_name(candidates, *needles)
        if picked and anchor and picked.lower() == anchor.lower() and "low" in "".join(needles):
            others = [name for name in candidates if name != anchor]
            return ComfyUIBackend._pick_name(others, *needles)
        return picked

    def _wan_sampler_settings(
        self, params: GenerationParams, bundle: dict[str, Any]
    ) -> tuple[int, float, str, str, bool]:
        lightning = bool(bundle.get("lightning"))
        if lightning:
            steps = params.steps if 4 <= params.steps <= 8 else 4
            cfg = 1.0
            sampler = "euler"
            scheduler = "simple"
            return steps, cfg, sampler, scheduler, True
        steps = max(params.steps, 20)
        cfg = params.cfg_scale if 0 < params.cfg_scale <= 6 else 3.5
        sampler = params.sampler if params.sampler else "euler"
        scheduler = params.scheduler if params.scheduler else "simple"
        return steps, cfg, sampler, scheduler, False

    @staticmethod
    def _align(value: int, step: int, minimum: int, maximum: int) -> int:
        value = max(minimum, min(maximum, int(value)))
        aligned = int(round(value / step) * step)
        aligned = max(step, aligned)
        return min(maximum, aligned)

    @staticmethod
    def _wan_fps(fps: int | None) -> int:
        value = int(fps or 16)
        return max(4, min(value, 30))

    @staticmethod
    def _wan_shift(motion_bucket_id: int | None) -> float:
        # SVD-style 1..255 mapped onto Wan ModelSamplingSD3 shift.
        motion = max(1, min(255, int(motion_bucket_id or 127)))
        if motion <= 127:
            shift = 3.0 + (motion - 1) / 126.0 * 5.0
        else:
            shift = 8.0 + (motion - 127) / 128.0 * 4.0
        return round(shift, 2)

    def _wan_profile(self, family: str) -> dict[str, int]:
        if family == "ti2v_5b":
            return {"max_pixels": 768 * 432, "max_edge": 768, "max_length": 49, "step": 32}
        # 14B fp8 on 12GB: honor user size/length, cap at 480p-class and 81 frames (4n+1).
        return {"max_pixels": 640 * 480, "max_edge": 640, "max_length": 81, "step": 16}

    def _wan_dimensions(self, params: GenerationParams, family: str) -> tuple[int, int]:
        profile = self._wan_profile(family)
        step = profile["step"]
        width = max(step, int(params.width or 640))
        height = max(step, int(params.height or 384))
        max_pixels = profile["max_pixels"]
        max_edge = profile["max_edge"]
        scale = min(1.0, max_edge / max(width, height), (max_pixels / max(width * height, 1)) ** 0.5)
        width = self._align(int(width * scale), step, step, max_edge)
        height = self._align(int(height * scale), step, step, max_edge)
        while width * height > max_pixels and (width > step or height > step):
            if width >= height:
                width = max(step, width - step)
            else:
                height = max(step, height - step)
        return width, height

    def _wan_length(self, frames: int, family: str = "t2v") -> int:
        max_length = self._wan_profile(family)["max_length"]
        frames = max(9, min(int(frames or 25), max_length))
        count = round((frames - 1) / 4)
        return max(9, min(max_length, count * 4 + 1))

    def _default_checkpoint(self) -> str:
        if self._object_info:
            models = [
                model
                for model in self._list_from_object_info(self._object_info, "CheckpointLoaderSimple", "ckpt_name")
                if not self._is_video_checkpoint_name(model)
            ]
            if models:
                preferred = ("realisticvision", "juggernaut", "epicrealism", "realism")
                for needle in preferred:
                    for model in models:
                        if needle in model.lower():
                            return model
                return models[0]
        return "v1-5-pruned-emaonly.safetensors"

    def _default_video_model(self) -> str:
        if self._object_info:
            models = self._list_video_models(self._object_info)
            wan = [name for name in models if self._is_wan_name(name)]
            if wan:
                return self._pick_name(wan, "high", "t2v") or wan[0]
            if models:
                return models[0]
        raise RuntimeError(self._video_setup_error())

    def _default_svd_model(self) -> str:
        if self._object_info:
            models = self._svd_checkpoints(self._object_info)
            for preferred in ("svd_xt_1_1.safetensors", "svd_xt.safetensors", "svd.safetensors"):
                if preferred in models:
                    return preferred
            if models:
                return models[0]
        raise RuntimeError("No SVD video model found. Download svd_xt via Stability Matrix, or use the installed Wan 2.2 models.")

    async def _upload_image(self, image_b64: str) -> str:
        raw = base64.b64decode(image_b64)
        filename = f"local_studio_{uuid.uuid4().hex}.png"
        files = {"image": (filename, raw, "image/png")}
        data = {"overwrite": "true"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/upload/image", files=files, data=data)
            response.raise_for_status()
            return response.json().get("name", filename)

    async def _upload_image_ref(self, ref: str) -> str:
        if ref.startswith("http"):
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(ref)
                resp.raise_for_status()
                return await self._upload_image(base64.b64encode(resp.content).decode("ascii"))
        return await self._upload_image(ref)

    async def _run_workflow(
        self,
        workflow: dict[str, Any],
        params: GenerationParams,
        expect_video: bool = False,
    ) -> GenerationResult:
        seed = self._sampler_seed(workflow)
        client_id = str(uuid.uuid4())

        async with httpx.AsyncClient(timeout=900.0) as client:
            prompt_resp = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            prompt_resp.raise_for_status()
            payload = prompt_resp.json()
            self._raise_prompt_errors(payload)
            prompt_id = payload["prompt_id"]

        progress_state.update(2, f"Queued in ComfyUI ({prompt_id[:8]}...)")
        media = await self._wait_for_outputs(client_id, prompt_id)
        images = media.get("images", [])
        videos = media.get("videos", [])

        if expect_video and not videos and images:
            videos = images
            images = []
        if expect_video and not videos:
            raise RuntimeError("ComfyUI finished without a video file. Check the ComfyUI log for VAE or sampler errors.")

        seeds = [seed + i for i in range(max(len(images), len(videos), 1))]
        return GenerationResult(
            images=images,
            videos=videos,
            seeds=seeds,
            metadata={"backend": "comfyui", "mode": params.mode, "prompt_id": prompt_id},
        )

    @staticmethod
    def _raise_prompt_errors(payload: dict[str, Any]) -> None:
        error = payload.get("error")
        if error:
            if isinstance(error, dict):
                message = error.get("message") or error.get("details") or str(error)
            else:
                message = str(error)
            raise RuntimeError(f"ComfyUI rejected the workflow: {message}")
        node_errors = payload.get("node_errors") or {}
        if node_errors:
            parts = []
            for node_id, detail in node_errors.items():
                if isinstance(detail, dict):
                    parts.append(f"{node_id}: {detail.get('errors') or detail}")
                else:
                    parts.append(f"{node_id}: {detail}")
            raise RuntimeError("ComfyUI node errors: " + "; ".join(parts))

    async def _wait_for_outputs(self, client_id: str, prompt_id: str) -> dict[str, list[str]]:
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        done = asyncio.Event()
        ws_error: dict[str, str] = {}

        async def listen() -> None:
            try:
                async with websockets.connect(f"{ws_url}/ws?clientId={client_id}") as ws:
                    while not done.is_set():
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=900.0)
                        except asyncio.TimeoutError:
                            break
                        if isinstance(message, bytes):
                            continue
                        data = json.loads(message)
                        msg_type = data.get("type")
                        payload = data.get("data", {})

                        if msg_type == "progress" and payload.get("prompt_id") == prompt_id:
                            value = int(payload.get("value", 0))
                            maximum = int(payload.get("max", 1)) or 1
                            percent = round((value / maximum) * 100)
                            node = payload.get("node") or "sampler"
                            progress_state.update(
                                percent,
                                f"Sampling step {value}/{maximum} (node {node})",
                            )
                        elif msg_type == "execution_error" and payload.get("prompt_id") == prompt_id:
                            node_type = payload.get("node_type") or payload.get("node_id") or "node"
                            message = (payload.get("exception_message") or "execution error").strip()
                            ws_error["message"] = f"ComfyUI {node_type} failed: {message}"
                            done.set()
                            break
                        elif msg_type == "executing":
                            node = payload.get("node")
                            if node is None and payload.get("prompt_id") == prompt_id:
                                progress_state.update(100, "Finalizing output...")
                                done.set()
                                break
                            if node and payload.get("prompt_id") == prompt_id:
                                progress_state.update(
                                    max(progress_state.percent, 5),
                                    f"Running node {node}...",
                                )
                        elif msg_type == "execution_start" and payload.get("prompt_id") == prompt_id:
                            progress_state.update(3, "ComfyUI started workflow")
            except Exception:
                done.set()

        listener = asyncio.create_task(listen())
        try:
            for _ in range(900):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    history_resp = await client.get(f"{self.base_url}/history/{prompt_id}")
                    if history_resp.status_code == 200:
                        history = history_resp.json()
                        if prompt_id in history:
                            entry = history[prompt_id]
                            error = self._history_error(entry) or ws_error.get("message")
                            if error:
                                raise RuntimeError(error)
                            status = entry.get("status") or {}
                            if status.get("completed") or entry.get("outputs"):
                                done.set()
                                return self._extract_outputs(entry)
                if done.is_set():
                    if ws_error.get("message"):
                        raise RuntimeError(ws_error["message"])
                    break
                await asyncio.sleep(1)
            if ws_error.get("message"):
                raise RuntimeError(ws_error["message"])
            raise TimeoutError("ComfyUI generation timed out")
        finally:
            done.set()
            listener.cancel()

    @staticmethod
    def _history_error(entry: dict[str, Any]) -> str | None:
        status = entry.get("status") or {}
        if status.get("status_str") != "error":
            return None
        for item in status.get("messages") or []:
            if not (isinstance(item, list) and item and item[0] == "execution_error"):
                continue
            payload = item[1] if len(item) > 1 and isinstance(item[1], dict) else {}
            node_type = payload.get("node_type") or payload.get("node_id") or "node"
            message = (payload.get("exception_message") or "execution error").strip()
            return f"ComfyUI {node_type} failed: {message}"
        return "ComfyUI execution error"

    def _extract_outputs(self, history_entry: dict[str, Any]) -> dict[str, list[str]]:
        images: list[str] = []
        videos: list[str] = []
        outputs = history_entry.get("outputs", {})

        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for key in ("images", "gifs", "videos", "animated"):
                for media_info in node_output.get(key, []) or []:
                    if not isinstance(media_info, dict) or "filename" not in media_info:
                        continue
                    url = self._media_url(media_info)
                    if self._is_video_output(media_info):
                        videos.append(url)
                    elif key == "images":
                        images.append(url)
                    else:
                        videos.append(url)

        return {"images": images, "videos": videos}

    @staticmethod
    def _is_video_output(info: dict[str, Any]) -> bool:
        filename = str(info.get("filename") or "").lower()
        fmt = str(info.get("format") or "").lower()
        return (
            "video" in fmt
            or bool(info.get("animated"))
            or filename.endswith(_VIDEO_FILE_SUFFIXES)
        )

    def _media_url(self, info: dict[str, Any]) -> str:
        filename = info["filename"]
        subfolder = info.get("subfolder", "")
        media_type = info.get("type", "output")
        return f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={media_type}"
