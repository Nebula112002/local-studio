from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT_DIR / "profiles.json"


class CharacterProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    # Core appearance traits for consistent character generation
    hair: str = ""
    eyes: str = ""
    skin_tone: str = ""
    body_type: str = ""
    age_range: str = "young adult"
    ethnicity: str = ""
    distinctive_features: str = ""
    # Style & defaults
    art_style: str = "photorealistic"
    default_outfit: str = ""
    personality_vibe: str = ""
    # Prompt building
    prompt_prefix: str = ""
    negative_prompt: str = (
        "low quality, worst quality, blurry, deformed, bad anatomy, "
        "extra limbs, watermark, text, logo"
    )
    # Generation preferences
    preferred_model: str | None = None
    preferred_seed: int = -1
    preferred_width: int = 1024
    preferred_height: int = 1024
    preferred_steps: int = 30
    preferred_cfg: float = 7.0
    preferred_sampler: str = "dpmpp_2m"
    preferred_scheduler: str = "karras"
    clip_skip: int = 2
    # Saved scene ideas (one-liner prompts)
    scene_ideas: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    thumbnail: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def build_appearance_prompt(self) -> str:
        """Assemble a consistent appearance block from trait fields."""
        parts: list[str] = []
        if self.prompt_prefix.strip():
            parts.append(self.prompt_prefix.strip())

        traits: list[str] = []
        if self.age_range:
            traits.append(self.age_range)
        if self.ethnicity:
            traits.append(self.ethnicity)
        if self.hair:
            traits.append(f"{self.hair} hair")
        if self.eyes:
            traits.append(f"{self.eyes} eyes")
        if self.skin_tone:
            traits.append(f"{self.skin_tone} skin")
        if self.body_type:
            traits.append(self.body_type)
        if self.distinctive_features:
            traits.append(self.distinctive_features)
        if self.default_outfit:
            traits.append(f"wearing {self.default_outfit}")

        if traits:
            parts.append(", ".join(traits))

        if self.art_style:
            parts.append(self.art_style)

        return ", ".join(p for p in parts if p)

    def to_generation_defaults(self) -> dict[str, Any]:
        return {
            "prompt_prefix": self.build_appearance_prompt(),
            "negative_prompt": self.negative_prompt,
            "model": self.preferred_model,
            "seed": self.preferred_seed,
            "width": self.preferred_width,
            "height": self.preferred_height,
            "steps": self.preferred_steps,
            "cfg_scale": self.preferred_cfg,
            "sampler": self.preferred_sampler,
            "scheduler": self.preferred_scheduler,
            "clip_skip": self.clip_skip,
        }


def _load_raw() -> list[dict[str, Any]]:
    if not PROFILES_PATH.exists():
        return []
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


def _save_raw(profiles: list[dict[str, Any]]) -> None:
    PROFILES_PATH.write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_profiles() -> list[CharacterProfile]:
    return [CharacterProfile(**p) for p in _load_raw()]


def get_profile(profile_id: str) -> CharacterProfile | None:
    for raw in _load_raw():
        if raw.get("id") == profile_id:
            return CharacterProfile(**raw)
    return None


def create_profile(data: dict[str, Any]) -> CharacterProfile:
    profile = CharacterProfile(**data)
    profiles = _load_raw()
    profiles.append(profile.model_dump())
    _save_raw(profiles)
    return profile


def update_profile(profile_id: str, data: dict[str, Any]) -> CharacterProfile | None:
    profiles = _load_raw()
    for index, raw in enumerate(profiles):
        if raw.get("id") == profile_id:
            merged = {**raw, **data, "id": profile_id}
            merged["updated_at"] = datetime.now(timezone.utc).isoformat()
            profile = CharacterProfile(**merged)
            profiles[index] = profile.model_dump()
            _save_raw(profiles)
            return profile
    return None


def delete_profile(profile_id: str) -> bool:
    profiles = _load_raw()
    filtered = [p for p in profiles if p.get("id") != profile_id]
    if len(filtered) == len(profiles):
        return False
    _save_raw(filtered)
    return True
