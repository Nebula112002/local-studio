from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server.backends import Automatic1111Backend, ComfyUIBackend
from server.paths import agent_output_dir
from server.backends.base import BackendInfo, BaseBackend, GenerationParams, GenerationResult
from server.history import (
    delete_history_bulk,
    delete_history_item,
    list_history,
    record_generation,
    scan_output_files,
)
from server.hosts import LOCAL_URL, PORT, TAILNET_URL, service_urls
from server.profile_assets import (
    delete_assets,
    get_reference_b64,
    get_thumbnail_b64,
    has_reference,
    save_reference,
    save_thumbnail,
)
from server.profile_templates import get_template, list_templates
from server.presets import get_preset, list_presets, list_social_presets, list_video_presets
from server.profiles import (
    CharacterProfile,
    create_profile,
    delete_profile,
    duplicate_profile,
    get_profile,
    list_profiles,
    update_profile,
)
from server.progress import progress_state
from server.prompt_assistant import (
    DEFAULT_OLLAMA_MODEL,
    AssistantSettings,
    EnhanceRequest,
    check_assistant_status,
    run_assistant,
)
from server.proxy import proxy_comfyui_request
from server.queue import BatchRequest, JobQueue
from server.stability_matrix import find_stability_matrix_exe, probe_comfyui, resolve_stability_matrix_paths

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
OUTPUT_DIR = agent_output_dir()
CONFIG_PATH = ROOT_DIR / "config.json"

DEFAULT_BACKENDS = {
    "comfyui": "http://127.0.0.1:8188",
    "automatic1111": "http://127.0.0.1:7860",
}

app = FastAPI(title="Local Studio", version="2.0.0")
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
    stability_matrix_path: str = ""
    save_to_disk: bool = True
    # Local LLM prompt assistant (Ollama or OpenAI-compatible)
    assistant_enabled: bool = True
    assistant_provider: str = "ollama"
    assistant_url: str = "http://127.0.0.1:11434"
    assistant_model: str = DEFAULT_OLLAMA_MODEL
    assistant_api_key: str = ""
    assistant_temperature: float = 0.8


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
    profile_id: str | None = None
    profile_name: str | None = None


class ImageUpload(BaseModel):
    image: str  # base64


class BatchScenesRequest(BaseModel):
    profile_id: str
    seed_mode: str = "increment"
    mode: Literal["txt2img", "img2img"] = "txt2img"
    use_reference: bool = True


class BatchGenerateRequest(GenerateRequest):
    batch_count: int = Field(default=1, ge=1, le=100)
    seed_mode: str = "increment"
    prompt_variations: list[str] = Field(default_factory=list)
    use_variation_suffix: bool = True


def load_settings() -> SettingsModel:
    if CONFIG_PATH.exists():
        # utf-8-sig tolerates a BOM from Windows editors / PowerShell Set-Content
        settings = SettingsModel(**json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
    else:
        settings = SettingsModel()
    if settings.assistant_model == "llama3.2":
        settings.assistant_model = DEFAULT_OLLAMA_MODEL
        save_settings(settings)
    return settings


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
        detail=(
            "ComfyUI is not running. Start it manually from Stability Matrix → Packages → ComfyUI → Launch. "
            "Local Studio never auto-starts ComfyUI."
        ),
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
    saved_files: list[str] = []

    for image in result.images:
        images.append(await _fetch_b64(image) if image.startswith("http") else image)

    for video in result.videos:
        videos.append(await _fetch_b64(video) if video.startswith("http") else video)

    # Always persist media so History can show thumbnails (and Delete can remove files).
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = result.seeds[0] if result.seeds else params.seed
    for index, image_b64 in enumerate(images):
        filename = OUTPUT_DIR / f"{params.mode}_{stamp}_{index}.png"
        filename.write_bytes(base64.b64decode(image_b64))
        saved_files.append(filename.name)
    for index, video_b64 in enumerate(videos):
        filename = OUTPUT_DIR / f"{params.mode}_{stamp}_{index}.mp4"
        filename.write_bytes(base64.b64decode(video_b64))
        saved_files.append(filename.name)

    # Always record generation history
    extra = getattr(params, "_history_meta", {})
    media_type = "video" if videos else "image"
    record_generation(
        mode=params.mode,
        prompt=params.prompt,
        negative_prompt=params.negative_prompt,
        seeds=result.seeds,
        width=params.width,
        height=params.height,
        steps=params.steps,
        cfg_scale=params.cfg_scale,
        sampler=params.sampler,
        model=params.model,
        files=saved_files,
        media_type=media_type,
        profile_id=extra.get("profile_id"),
        profile_name=extra.get("profile_name"),
    )

    return GenerationResult(
        images=images,
        videos=videos,
        seeds=result.seeds,
        metadata={**(result.metadata or {}), "files": saved_files},
    )


async def generate_with_backend(params: GenerationParams) -> GenerationResult:
    backend, backend_type = await get_backend()
    info = await backend.get_info()
    if params.mode not in info.capabilities:
        raise RuntimeError(
            f"Mode '{params.mode}' is not supported by {info.name}. "
            f"Available: {', '.join(info.capabilities)}"
        )
    progress_state.start(f"Generating {params.mode} via {info.name}...")
    try:
        result = await backend.generate(params)
        normalized = await _normalize_result(result, params)
        progress_state.finish("Generation complete")
        return normalized
    except Exception as exc:
        progress_state.fail(str(exc))
        raise


queue.set_generator(generate_with_backend)


@app.on_event("startup")
async def startup() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    backend_status: dict[str, Any] = {"connected": False}
    try:
        backend, backend_type = await get_backend()
        info = await backend.get_info()
        backend_status = {
            "connected": True,
            "type": backend_type,
            "name": info.name,
            "capabilities": info.capabilities,
            "model_count": len(info.models),
        }
    except HTTPException:
        pass

    assistant_status = await check_assistant_status(_assistant_settings())

    return {
        "status": "ok",
        "version": "2.0.0",
        "port": PORT,
        "local": LOCAL_URL,
        "tailnet": TAILNET_URL,
        "links": {
            "local": LOCAL_URL,
            "tailnet": TAILNET_URL,
            "comfyui": load_settings().comfyui_url,
            "automatic1111": load_settings().automatic1111_url,
        },
        "backend": backend_status,
        "assistant": assistant_status,
        "profiles_count": len(list_profiles()),
        **service_urls(),
    }


@app.get("/api/progress")
async def generation_progress() -> dict[str, Any]:
    return {
        "active": progress_state.active,
        "percent": progress_state.percent,
        "message": progress_state.message,
        "log": progress_state.log,
    }


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


@app.get("/api/image-lab")
async def image_lab_info() -> dict[str, Any]:
    settings = load_settings()
    comfyui_url = settings.comfyui_url.rstrip("/")
    comfyui = await probe_comfyui(comfyui_url)
    sm_paths = resolve_stability_matrix_paths(settings.stability_matrix_path or None)

    return {
        "comfyui_url": comfyui_url,
        "comfyui_connected": comfyui["connected"],
        "comfyui_status": comfyui["status"],
        "comfyui_message": comfyui["message"],
        "comfyui_hint": comfyui.get("hint", ""),
        "comfyui_port_open": comfyui.get("port_open", False),
        "embed_url": "/proxy/comfyui/",
        "comfyui_direct_url": comfyui_url,
        "stability_matrix": sm_paths.as_dict(),
        "duplicate_comfyui_warning": (
            "Local Studio never starts ComfyUI automatically. "
            "If port 8188 is in use or you see a database lock, ComfyUI is already running — "
            "do not click Launch again in Stability Matrix."
        ),
    }


@app.post("/api/image-lab/launch")
async def launch_stability_matrix() -> dict[str, str]:
    settings = load_settings()
    sm_exe = find_stability_matrix_exe(settings.stability_matrix_path or None)
    if not sm_exe:
        raise HTTPException(
            status_code=404,
            detail=(
                "Stability Matrix not found. Set stability_matrix_path in Settings or "
                "STABILITY_MATRIX_PATH env var."
            ),
        )

    comfyui = await probe_comfyui(settings.comfyui_url)
    import subprocess

    subprocess.Popen([sm_exe], close_fds=True)
    return {
        "status": "launched",
        "path": sm_exe,
        "comfyui_started": False,
        "comfyui_already_running": comfyui["connected"],
        "note": (
            "Opened Stability Matrix only — ComfyUI was NOT started. "
            "ComfyUI is already running on port 8188."
            if comfyui["connected"]
            else (
                "Opened Stability Matrix only — ComfyUI was NOT started. "
                "Launch ComfyUI yourself from Packages → ComfyUI when you are ready."
            )
        ),
    }


@app.api_route("/proxy/comfyui/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def comfyui_proxy(path: str, request: Request) -> Response:
    settings = load_settings()
    return await proxy_comfyui_request(settings.comfyui_url, path, request)


@app.get("/api/backend")
async def backend_info() -> dict[str, Any]:
    settings = load_settings()
    comfyui = await probe_comfyui(settings.comfyui_url)
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
            "comfyui_status": comfyui["status"],
            "comfyui_message": comfyui["message"],
        }
    except HTTPException as exc:
        return {
            "connected": False,
            "error": exc.detail,
            "comfyui_status": comfyui["status"],
            "comfyui_message": comfyui["message"],
            "comfyui_hint": comfyui.get("hint", ""),
        }


@app.post("/api/generate")
async def generate_once(request: GenerateRequest) -> dict[str, Any]:
    params = GenerationParams(**request.model_dump(exclude={"profile_id", "profile_name"}))
    params._history_meta = {"profile_id": request.profile_id, "profile_name": request.profile_name}  # type: ignore[attr-defined]
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


def _assistant_settings() -> AssistantSettings:
    s = load_settings()
    return AssistantSettings(
        enabled=s.assistant_enabled,
        provider=s.assistant_provider,  # type: ignore[arg-type]
        base_url=s.assistant_url,
        model=s.assistant_model,
        api_key=s.assistant_api_key,
        temperature=s.assistant_temperature,
    )


@app.get("/api/presets")
async def presets_list() -> dict[str, Any]:
    return {"image": list_presets(), "video": list_video_presets(), "social": list_social_presets()}


@app.get("/api/presets/{preset_id}")
async def presets_get(preset_id: str) -> dict[str, Any]:
    preset = get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@app.get("/api/profiles")
async def profiles_list() -> list[dict[str, Any]]:
    result = []
    for p in list_profiles():
        data = p.model_dump()
        thumb = get_thumbnail_b64(p.id)
        if thumb:
            data["thumbnail"] = thumb
        data["has_reference"] = has_reference(p.id)
        result.append(data)
    return result


@app.get("/api/profiles/templates/list")
async def profiles_templates() -> list[dict[str, Any]]:
    return list_templates()


@app.post("/api/profiles/templates/{template_id}")
async def profiles_from_template(template_id: str) -> dict[str, Any]:
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    created = create_profile(template)
    return created.model_dump()


@app.post("/api/profiles")
async def profiles_create(profile: CharacterProfile) -> dict[str, Any]:
    created = create_profile(profile.model_dump(exclude_none=True))
    return created.model_dump()


@app.post("/api/profiles/{profile_id}/duplicate")
async def profiles_duplicate(profile_id: str) -> dict[str, Any]:
    dup = duplicate_profile(profile_id)
    if not dup:
        raise HTTPException(status_code=404, detail="Profile not found")
    ref = get_reference_b64(profile_id)
    thumb = get_thumbnail_b64(profile_id)
    if ref:
        save_reference(dup.id, ref)
    if thumb:
        save_thumbnail(dup.id, thumb)
    return dup.model_dump()


@app.post("/api/profiles/{profile_id}/reference")
async def profiles_set_reference(profile_id: str, body: ImageUpload) -> dict[str, str]:
    if not get_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    save_reference(profile_id, body.image)
    return {"status": "saved"}


@app.get("/api/profiles/{profile_id}/reference")
async def profiles_get_reference(profile_id: str) -> dict[str, Any]:
    if not get_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    ref = get_reference_b64(profile_id)
    if not ref:
        raise HTTPException(status_code=404, detail="No reference image")
    return {"image": ref}


@app.post("/api/profiles/{profile_id}/thumbnail")
async def profiles_set_thumbnail(profile_id: str, body: ImageUpload) -> dict[str, str]:
    if not get_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    save_thumbnail(profile_id, body.image)
    return {"status": "saved"}


@app.post("/api/profiles/batch-scenes")
async def profiles_batch_scenes(request: BatchScenesRequest) -> dict[str, Any]:
    profile = get_profile(request.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not profile.scene_ideas:
        raise HTTPException(status_code=400, detail="No saved scene ideas on this character")

    defaults = profile.to_generation_defaults()
    init_image = None
    if request.use_reference and request.mode == "img2img":
        init_image = get_reference_b64(request.profile_id)

    base_params = GenerationParams(
        prompt=defaults["prompt_prefix"],
        negative_prompt=defaults["negative_prompt"],
        mode=request.mode,
        width=defaults["width"],
        height=defaults["height"],
        steps=defaults["steps"],
        cfg_scale=defaults["cfg_scale"],
        sampler=defaults["sampler"],
        scheduler=defaults["scheduler"],
        seed=defaults["seed"],
        model=defaults["model"],
        clip_skip=defaults["clip_skip"],
        init_image=init_image,
    )
    base_params._history_meta = {"profile_id": profile.id, "profile_name": profile.name}  # type: ignore[attr-defined]

    batch = BatchRequest(
        base_params=base_params,
        batch_count=1,
        seed_mode=request.seed_mode,
        prompt_variations=profile.scene_ideas,
        use_variation_suffix=True,
        variations_only=True,
    )
    job_ids = await queue.enqueue_batch(batch)
    return {"job_ids": job_ids, "count": len(job_ids), "scenes": profile.scene_ideas}


@app.get("/api/profiles/{profile_id}")
async def profiles_get(profile_id: str) -> dict[str, Any]:
    profile = get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump()


@app.put("/api/profiles/{profile_id}")
async def profiles_update(profile_id: str, profile: CharacterProfile) -> dict[str, Any]:
    updated = update_profile(profile_id, profile.model_dump(exclude={"id"}, exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")
    return updated.model_dump()


@app.delete("/api/profiles/{profile_id}")
async def profiles_delete(profile_id: str) -> dict[str, str]:
    if not delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    delete_assets(profile_id)
    return {"status": "deleted"}


@app.get("/api/profiles/{profile_id}/defaults")
async def profiles_defaults(profile_id: str) -> dict[str, Any]:
    profile = get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.to_generation_defaults()


@app.get("/api/assistant/status")
async def assistant_status() -> dict[str, Any]:
    return await check_assistant_status(_assistant_settings())


@app.post("/api/assistant/enhance")
async def assistant_enhance(request: EnhanceRequest) -> dict[str, Any]:
    try:
        return await run_assistant(_assistant_settings(), request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM request failed: {exc}. Is Ollama running? Try: ollama pull {load_settings().assistant_model}",
        ) from exc


@app.get("/api/history")
async def history_list(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return list_history(limit=limit, offset=offset)


class ClearHistoryRequest(BaseModel):
    within_hours: float | None = Field(default=None, gt=0, le=24 * 365)
    clear_all: bool = False


@app.post("/api/history/clear")
async def history_clear(request: ClearHistoryRequest) -> dict[str, Any]:
    if not request.clear_all and request.within_hours is None:
        raise HTTPException(status_code=400, detail="Choose within_hours or clear_all")
    try:
        result = delete_history_bulk(
            within_hours=None if request.clear_all else request.within_hours,
            clear_all=request.clear_all,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "cleared", **result}


@app.delete("/api/history/{item_id}")
async def history_delete(item_id: str) -> dict[str, Any]:
    result = delete_history_item(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="History item not found")
    return {"status": "deleted", **result}


@app.get("/api/output")
async def output_list() -> list[dict[str, Any]]:
    return scan_output_files()


@app.delete("/api/output/{filename}")
async def output_delete(filename: str) -> dict[str, Any]:
    safe_name = Path(filename).name
    path = (OUTPUT_DIR / safe_name).resolve()
    try:
        path.relative_to(OUTPUT_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename") from exc
    removed = 0
    if path.is_file():
        path.unlink()
        removed = 1

    # Drop history rows that only referenced this file (or scrub the file from lists).
    from server.history import _load_index, _save_index

    index = _load_index()
    next_index = []
    for entry in index:
        files = [f for f in (entry.get("files") or []) if Path(str(f)).name != safe_name]
        if not files and entry.get("files"):
            continue
        entry = {**entry, "files": files}
        next_index.append(entry)
    _save_index(next_index)

    if removed == 0:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted", "filename": safe_name, "files_removed": removed}


@app.get("/api/output/{filename}")
async def output_file(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = OUTPUT_DIR / safe_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".webp": "image/webp", ".mp4": "video/mp4", ".webm": "video/webm", ".gif": "image/gif"}
    return FileResponse(path, media_type=media_types.get(path.suffix.lower(), "application/octet-stream"))


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
