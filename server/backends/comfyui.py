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
        lowered = name.lower()
        return any(token in lowered for token in ("svd", "wan", "ti2v", "i2v", "video2"))

    async def get_info(self) -> BackendInfo:
        info = await self._fetch_object_info()
        models = [
            model
            for model in self._list_from_object_info(info, "CheckpointLoaderSimple", "ckpt_name")
            if not self._is_video_checkpoint_name(model)
        ]
        samplers = self._list_from_object_info(info, "KSampler", "sampler_name")
        schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        video_models = self._list_from_object_info(info, "ImageOnlyCheckpointLoader", "ckpt_name")

        capabilities = ["txt2img", "img2img"]
        if "SVD_img2vid_Conditioning" in info:
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
        if params.mode == "img2video":
            if not params.init_image:
                raise ValueError("Image-to-video requires a source image.")
            if "img2video" not in info.capabilities:
                raise RuntimeError(
                    "Image-to-video needs ComfyUI with SVD nodes. "
                    "Install an SVD checkpoint (e.g. svd_xt) via Stability Matrix."
                )
            uploaded = await self._upload_image(params.init_image)
            return await self._run_workflow(self._build_svd_workflow(params, uploaded), params, expect_video=True)
        if params.mode == "txt2video":
            if "txt2video" not in info.capabilities:
                raise RuntimeError(
                    "Text-to-video needs ComfyUI with SVD. "
                    "Install svd_xt via Stability Matrix, then use ComfyUI backend."
                )
            still = await self._run_workflow(self._build_txt2img_workflow(params), params)
            if not still.images:
                raise RuntimeError("Failed to generate starting frame for video.")
            uploaded = await self._upload_image_ref(still.images[0])
            video = await self._run_workflow(self._build_svd_workflow(params, uploaded), params, expect_video=True)
            video.images = still.images[:1]
            video.metadata["start_frame_seed"] = still.seeds[0] if still.seeds else params.seed
            return video

        raise ValueError(f"Unsupported mode: {params.mode}")

    def _build_txt2img_workflow(self, params: GenerationParams) -> dict[str, Any]:
        seed = params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)
        model = params.model or self._default_checkpoint()
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": params.steps,
                    "cfg": params.cfg_scale,
                    "sampler_name": params.sampler,
                    "scheduler": params.scheduler,
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

    def _build_img2img_workflow(self, params: GenerationParams, image_name: str) -> dict[str, Any]:
        seed = params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)
        model = params.model or self._default_checkpoint()
        return {
            "10": {"class_type": "LoadImage", "inputs": {"image": image_name}},
            "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["4", 2]}},
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": params.steps,
                    "cfg": params.cfg_scale,
                    "sampler_name": params.sampler,
                    "scheduler": params.scheduler,
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

    def _build_svd_workflow(self, params: GenerationParams, image_name: str) -> dict[str, Any]:
        seed = params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)
        video_model = params.video_model or self._default_video_model()
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
                    "scheduler": "karras",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["3", 1],
                    "latent_image": ["3", 2],
                },
            },
            "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        }

        if self._object_info and "CreateVideo" in self._object_info:
            workflow["6"] = {
                "class_type": "CreateVideo",
                "inputs": {"images": ["5", 0], "fps": params.fps},
            }
            workflow["7"] = {
                "class_type": "SaveVideo",
                "inputs": {"filename_prefix": "local_studio", "video": ["6", 0], "format": "mp4", "codec": "h264"},
            }
        elif self._object_info and "VHS_VideoCombine" in self._object_info:
            workflow["6"] = {
                "class_type": "VHS_VideoCombine",
                "inputs": {
                    "images": ["5", 0],
                    "frame_rate": params.fps,
                    "loop_count": 0,
                    "filename_prefix": "local_studio",
                    "format": "video/h264-mp4",
                    "pingpong": False,
                    "save_output": True,
                },
            }
        else:
            workflow["6"] = {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "local_studio_frames", "images": ["5", 0]},
            }

        return workflow

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
            models = self._list_from_object_info(self._object_info, "ImageOnlyCheckpointLoader", "ckpt_name")
            for preferred in ("svd_xt_1_1.safetensors", "svd_xt.safetensors", "svd.safetensors"):
                if preferred in models:
                    return preferred
            if models:
                return models[0]
        raise RuntimeError("No SVD video model found. Download svd_xt via Stability Matrix.")

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
        seed = params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)
        client_id = str(uuid.uuid4())

        async with httpx.AsyncClient(timeout=900.0) as client:
            prompt_resp = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            prompt_resp.raise_for_status()
            prompt_id = prompt_resp.json()["prompt_id"]

        progress_state.update(2, f"Queued in ComfyUI ({prompt_id[:8]}...)")
        media = await self._wait_for_outputs(client_id, prompt_id)
        images = media.get("images", [])
        videos = media.get("videos", [])

        if expect_video and not videos and images:
            videos = images
            images = []

        seeds = [seed + i for i in range(max(len(images), len(videos), 1))]
        return GenerationResult(
            images=images,
            videos=videos,
            seeds=seeds,
            metadata={"backend": "comfyui", "mode": params.mode, "prompt_id": prompt_id},
        )

    async def _wait_for_outputs(self, client_id: str, prompt_id: str) -> dict[str, list[str]]:
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        done = asyncio.Event()

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
                if done.is_set():
                    break
                await asyncio.sleep(1)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    history_resp = await client.get(f"{self.base_url}/history/{prompt_id}")
                    if history_resp.status_code == 200:
                        history = history_resp.json()
                        if prompt_id in history:
                            done.set()
                            return self._extract_outputs(history[prompt_id])
            raise TimeoutError("ComfyUI generation timed out")
        finally:
            done.set()
            listener.cancel()

    def _extract_outputs(self, history_entry: dict[str, Any]) -> dict[str, list[str]]:
        images: list[str] = []
        videos: list[str] = []
        outputs = history_entry.get("outputs", {})

        for node_output in outputs.values():
            for image_info in node_output.get("images", []):
                url = self._media_url(image_info)
                fmt = image_info.get("format", "")
                if "video" in fmt or image_info.get("animated"):
                    videos.append(url)
                else:
                    images.append(url)

            for gif_info in node_output.get("gifs", []):
                videos.append(self._media_url(gif_info))

        return {"images": images, "videos": videos}

    def _media_url(self, info: dict[str, Any]) -> str:
        filename = info["filename"]
        subfolder = info.get("subfolder", "")
        media_type = info.get("type", "output")
        return f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={media_type}"
