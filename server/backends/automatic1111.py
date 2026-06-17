from __future__ import annotations

import random
from typing import Any

import httpx

from .base import BackendInfo, BaseBackend, GenerationParams, GenerationResult


class Automatic1111Backend(BaseBackend):
    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/sdapi/v1/options")
                return response.status_code == 200
        except Exception:
            return False

    async def get_info(self) -> BackendInfo:
        models: list[str] = []
        samplers: list[str] = []
        schedulers: list[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            models_resp = await client.get(f"{self.base_url}/sdapi/v1/sd-models")
            if models_resp.status_code == 200:
                models = [m.get("title", m.get("model_name", "")) for m in models_resp.json()]

            samplers_resp = await client.get(f"{self.base_url}/sdapi/v1/samplers")
            if samplers_resp.status_code == 200:
                samplers = [s.get("name", "") for s in samplers_resp.json()]

            schedulers_resp = await client.get(f"{self.base_url}/sdapi/v1/schedulers")
            if schedulers_resp.status_code == 200:
                schedulers = [s.get("name", "") for s in schedulers_resp.json()]

        return BackendInfo(
            name="Automatic1111 / Forge",
            backend_type="automatic1111",
            url=self.base_url,
            models=models,
            samplers=samplers,
            schedulers=schedulers,
            capabilities=["txt2img", "img2img"],
        )

    async def generate(self, params: GenerationParams) -> GenerationResult:
        if params.mode in ("txt2video", "img2video"):
            raise RuntimeError(
                "Video generation needs ComfyUI with an SVD model. "
                "Switch backend to ComfyUI in Settings, or use Stability Matrix to launch it."
            )
        if params.mode == "img2img":
            return await self._img2img(params)
        return await self._txt2img(params)

    async def _txt2img(self, params: GenerationParams) -> GenerationResult:
        seed = params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)

        if params.model:
            await self._set_model(params.model)

        payload: dict[str, Any] = {
            "prompt": params.prompt,
            "negative_prompt": params.negative_prompt,
            "width": params.width,
            "height": params.height,
            "steps": params.steps,
            "cfg_scale": params.cfg_scale,
            "sampler_name": params.sampler,
            "scheduler": params.scheduler,
            "seed": seed,
            "batch_size": params.batch_size,
            "n_iter": 1,
            "save_images": False,
            "send_images": True,
        }

        if params.clip_skip > 1:
            payload["override_settings"] = {"CLIP_stop_at_last_layers": params.clip_skip}
            payload["override_settings_restore_afterwards"] = True

        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload)
            response.raise_for_status()
            data = response.json()

        images = data.get("images", [])
        seeds = [seed + i for i in range(len(images))]
        return GenerationResult(images=images, seeds=seeds, metadata={"backend": "automatic1111", "mode": "txt2img"})

    async def _img2img(self, params: GenerationParams) -> GenerationResult:
        if not params.init_image:
            raise ValueError("Image-to-image requires a source image.")

        seed = params.seed if params.seed >= 0 else random.randint(0, 2**32 - 1)

        if params.model:
            await self._set_model(params.model)

        payload: dict[str, Any] = {
            "prompt": params.prompt,
            "negative_prompt": params.negative_prompt,
            "width": params.width,
            "height": params.height,
            "steps": params.steps,
            "cfg_scale": params.cfg_scale,
            "sampler_name": params.sampler,
            "scheduler": params.scheduler,
            "seed": seed,
            "batch_size": params.batch_size,
            "n_iter": 1,
            "init_images": [params.init_image],
            "denoising_strength": params.denoise,
            "save_images": False,
            "send_images": True,
        }

        if params.clip_skip > 1:
            payload["override_settings"] = {"CLIP_stop_at_last_layers": params.clip_skip}
            payload["override_settings_restore_afterwards"] = True

        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(f"{self.base_url}/sdapi/v1/img2img", json=payload)
            response.raise_for_status()
            data = response.json()

        images = data.get("images", [])
        seeds = [seed + i for i in range(len(images))]
        return GenerationResult(
            images=images,
            seeds=seeds,
            metadata={"backend": "automatic1111", "mode": "img2img", "denoise": params.denoise},
        )

    async def _set_model(self, model_name: str) -> None:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.post(
                f"{self.base_url}/sdapi/v1/options",
                json={"sd_model_checkpoint": model_name},
            )
