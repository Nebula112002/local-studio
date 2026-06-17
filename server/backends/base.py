from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

GenerationMode = Literal["txt2img", "img2img", "txt2video", "img2video"]


@dataclass
class GenerationParams:
    prompt: str
    negative_prompt: str = ""
    mode: GenerationMode = "txt2img"
    width: int = 1024
    height: int = 1024
    steps: int = 28
    cfg_scale: float = 7.0
    sampler: str = "euler"
    scheduler: str = "normal"
    seed: int = -1
    batch_size: int = 1
    model: str | None = None
    clip_skip: int = 1
    # 0 = keep original, 1 = full redraw (img2img / img2video motion)
    denoise: float = 0.55
    init_image: str | None = None
    frames: int = 25
    fps: int = 8
    video_model: str | None = None
    motion_bucket_id: int = 127


@dataclass
class GenerationResult:
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    seeds: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendInfo:
    name: str
    backend_type: str
    url: str
    models: list[str] = field(default_factory=list)
    samplers: list[str] = field(default_factory=list)
    schedulers: list[str] = field(default_factory=list)
    video_models: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=lambda: ["txt2img"])


class BaseBackend(ABC):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @abstractmethod
    async def get_info(self) -> BackendInfo:
        ...

    @abstractmethod
    async def generate(self, params: GenerationParams) -> GenerationResult:
        ...

    def supports(self, info: BackendInfo, mode: GenerationMode) -> bool:
        return mode in info.capabilities
