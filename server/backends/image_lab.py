"""Stability Matrix Image Lab backend — ComfyUI health check, no workflow building."""

from __future__ import annotations

from server.stability_matrix import probe_comfyui

from .base import BackendInfo, BaseBackend, GenerationParams, GenerationResult


class ImageLabBackend(BaseBackend):
    """Image Lab runs inside Stability Matrix and uses ComfyUI under the hood.

    There is no public Image Lab HTTP API; this backend verifies ComfyUI is
    reachable (Image Lab's dependency) and directs users to the Image Lab UI.
    Local Studio connects to the existing ComfyUI instance — it never starts one.
    """

    def __init__(self, comfyui_url: str) -> None:
        super().__init__(comfyui_url)
        self.comfyui_url = comfyui_url.rstrip("/")

    async def is_available(self) -> bool:
        status = await probe_comfyui(self.comfyui_url)
        return bool(status.get("connected"))

    async def get_info(self) -> BackendInfo:
        return BackendInfo(
            name="Image Lab (Stability Matrix)",
            backend_type="image_lab",
            url=self.comfyui_url,
            models=[],
            samplers=[],
            schedulers=[],
            video_models=[],
            capabilities=["txt2img", "img2img"],
        )

    async def generate(self, params: GenerationParams) -> GenerationResult:
        raise RuntimeError(
            "Image Lab uses Stability Matrix's conversational interface — not the "
            "Local Studio API. Open the Image Lab tab here, or launch Image Lab in "
            "Stability Matrix (sidebar, v2.16+). ComfyUI must already be running on "
            "port 8188 — do not start a second instance. For batch/video generation, "
            "switch backend to ComfyUI or Forge in Settings."
        )
