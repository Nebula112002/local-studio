from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server.backends import Automatic1111Backend, ComfyUIBackend
from server.backends.base import BackendInfo, BaseBackend, GenerationParams, GenerationResult
from server.queue import BatchRequest, JobQueue

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
OUTPUT_DIR = ROOT_DIR / "output"
CONFIG_PATH = ROOT_DIR / "config.json"

DEFAULT_BACKENDS = {
    "comfyui": "http://127.0.0.1:8188",
    "automatic1111": "http://127.0.0.1:7860",
}

app = FastAPI(title="Local Studio", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

queue = JobQueue()
_active_backend: BaseBackend | None = None
_active_backend_type: str = "auto"


class SettingsModel(BaseModel):
    backend_type: str = "auto"
    comfyui_url: str = DEFAULT_BACKENDS["comfyui"]
    automatic1111_url: str = DEFAULT_BACKENDS["automatic1111"]
    save_to_disk: bool = True


class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    mode: Literal["txt2img", "img2img", "txt2video", "img2video"] = "txt2img"
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
    denoise: float = Field(default=0.55, ge=0.0, le=1.0)
    init_image: str | None = None
    frames: int = Field(default=25, ge=8, le=120)
    fps: int = Field(default=8, ge=1, le=60)
    video_model: str | None = None
    motion_bucket_id: int = Field(default=127, ge=1, le=255)


class BatchGenerateRequest(GenerateRequest):
    batch_count: int = Field(default=1, ge=1, le=100)
    seed_mode: str = "increment"
    prompt_variations: list[str] = Field(default_factory=list)
    use_variation_suffix: bool = True


def load_settings() -> SettingsModel:
    if CONFIG_PATH.exists():
        return SettingsModel(**json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return SettingsModel()


def save_settings(settings: SettingsModel) -> None:
    CONFIG_PATH.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


def _make_backend(backend_type: str, settings: SettingsModel) -> BaseBackend:
    if backend_type == "comfyui":
        return ComfyUIBackend(settings.comfyui_url)
    if backend_type == "automatic1111":
        return Automatic1111Backend(settings.automatic1111_url)
    raise ValueError(f"Unknown backend: {backend_type}")


async def _detect_backend(settings: SettingsModel) -> tuple[BaseBackend, str]:
    if settings.backend_type != "auto":
        backend = _make_backend(settings.backend_type, settings)
        if await backend.is_available():
            return backend, settings.backend_type
        raise HTTPException(status_code=503, detail=f"{settings.backend_type} is not reachable")

    for name in ("comfyui", "automatic1111"):
        backend = _make_backend(name, settings)
        if await backend.is_available():
            return backend, name

    raise HTTPException(
        status_code=503,
        detail="No backend found. Start ComfyUI (8188) or A1111/Forge (7860) via Stability Matrix.",
    )


async def get_backend() -> tuple[BaseBackend, str]:
    global _active_backend, _active_backend_type
    settings = load_settings()
    if _active_backend is None:
        _active_backend, _active_backend_type = await _detect_backend(settings)
    elif not await _active_backend.is_available():
        _active_backend, _active_backend_type = await _detect_backend(settings)
    return _active_backend, _active_backend_type


async def _fetch_b64(url: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("ascii")


async def _normalize_result(result: GenerationResult, params: GenerationParams) -> GenerationResult:
    images: list[str] = []
    videos: list[str] = []

    for image in result.images:
        images.append(await _fetch_b64(image) if image.startswith("http") else image)

    for video in result.videos:
        videos.append(await _fetch_b64(video) if video.startswith("http") else video)

    if load_settings().save_to_disk:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = result.seeds[0] if result.seeds else params.seed
        for index, image_b64 in enumerate(images):
            filename = OUTPUT_DIR / f"{params.mode}_{stamp}_{index}.png"
            filename.write_bytes(base64.b64decode(image_b64))
        for index, video_b64 in enumerate(videos):
            filename = OUTPUT_DIR / f"{params.mode}_{stamp}_{index}.mp4"
            filename.write_bytes(base64.b64decode(video_b64))

    return GenerationResult(images=images, videos=videos, seeds=result.seeds, metadata=result.metadata)


async def generate_with_backend(params: GenerationParams) -> GenerationResult:
    backend, backend_type = await get_backend()
    info = await backend.get_info()
    if params.mode not in info.capabilities:
        raise RuntimeError(
            f"Mode '{params.mode}' is not supported by {info.name}. "
            f"Available: {', '.join(info.capabilities)}"
        )
    result = await backend.generate(params)
    return await _normalize_result(result, params)


queue.set_generator(generate_with_backend)


@app.on_event("startup")
async def startup() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings")
async def get_settings() -> SettingsModel:
    return load_settings()


@app.post("/api/settings")
async def update_settings(settings: SettingsModel) -> SettingsModel:
    global _active_backend, _active_backend_type
    save_settings(settings)
    _active_backend = None
    _active_backend_type = settings.backend_type
    return settings


@app.get("/api/backend")
async def backend_info() -> dict[str, Any]:
    try:
        backend, backend_type = await get_backend()
        info = await backend.get_info()
        return {
            "connected": True,
            "type": backend_type,
            "name": info.name,
            "url": info.url,
            "models": info.models,
            "samplers": info.samplers,
            "schedulers": info.schedulers,
            "video_models": info.video_models,
            "capabilities": info.capabilities,
        }
    except HTTPException as exc:
        return {"connected": False, "error": exc.detail}


@app.post("/api/generate")
async def generate_once(request: GenerateRequest) -> dict[str, Any]:
    params = GenerationParams(**request.model_dump())
    try:
        result = await generate_with_backend(params)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "images": result.images,
        "videos": result.videos,
        "seeds": result.seeds,
        "metadata": result.metadata,
    }


@app.post("/api/batch")
async def generate_batch(request: BatchGenerateRequest) -> dict[str, Any]:
    if request.mode in ("txt2video", "img2video"):
        raise HTTPException(status_code=400, detail="Batch queue is not supported for video modes yet.")
    base_params = GenerationParams(**request.model_dump(exclude={
        "batch_count", "seed_mode", "prompt_variations", "use_variation_suffix"
    }))
    batch = BatchRequest(
        base_params=base_params,
        batch_count=request.batch_count,
        seed_mode=request.seed_mode,
        prompt_variations=request.prompt_variations,
        use_variation_suffix=request.use_variation_suffix,
    )
    job_ids = await queue.enqueue_batch(batch)
    return {"job_ids": job_ids, "count": len(job_ids)}


@app.get("/api/queue")
async def queue_status() -> dict[str, Any]:
    return {
        "status": queue.get_queue_status(),
        "jobs": queue.list_jobs(),
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return queue.serialize_job(job)


@app.post("/api/queue/cancel")
async def cancel_queue() -> dict[str, str]:
    queue.cancel_queue()
    return {"status": "cancelled"}


@app.post("/api/queue/clear")
async def clear_queue() -> dict[str, str]:
    queue.clear_completed()
    return {"status": "cleared"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
