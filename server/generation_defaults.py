from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent
GENERATION_PATH = ROOT_DIR / "generation.json"


class GenerationDefaults(BaseModel):
    model: str | None = None
    video_model: str | None = None
    sampler: str = "euler"
    scheduler: str = "normal"
    width: int = 1024
    height: int = 1024
    steps: int = 28
    cfg_scale: float = 7.0
    clip_skip: int = 1
    seed: int = -1
    lock_seed: bool = False
    batch_size: int = 1
    batch_count: int = 1
    seed_mode: str = "increment"
    frames: int = 25
    fps: int = 8
    motion_bucket_id: int = 127
    similarity: int = 45


def load_generation_defaults() -> GenerationDefaults:
    if not GENERATION_PATH.exists():
        return GenerationDefaults()
    try:
        return GenerationDefaults(**json.loads(GENERATION_PATH.read_text(encoding="utf-8-sig")))
    except (json.JSONDecodeError, OSError, ValueError):
        return GenerationDefaults()


def save_generation_defaults(defaults: GenerationDefaults) -> GenerationDefaults:
    GENERATION_PATH.write_text(defaults.model_dump_json(indent=2), encoding="utf-8")
    return defaults


def generation_defaults_exist() -> bool:
    return GENERATION_PATH.exists()
