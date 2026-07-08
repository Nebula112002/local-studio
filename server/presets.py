"""Quality presets with optimized generation parameters."""

from __future__ import annotations

from typing import Any

QUALITY_PRESETS: dict[str, dict[str, Any]] = {
    "photorealistic": {
        "label": "Photorealistic",
        "description": "Sharp, detailed realism — best for portrait/photo models",
        "steps": 30,
        "cfg_scale": 6.5,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "clip_skip": 2,
        "prompt_suffix": "masterpiece, best quality, highly detailed, photorealistic, 8k uhd, sharp focus, professional photography",
        "negative_prompt": (
            "low quality, worst quality, blurry, deformed, bad anatomy, extra limbs, "
            "watermark, text, logo, cartoon, anime, painting, illustration, "
            "oversaturated, plastic skin, doll-like"
        ),
    },
    "cinematic": {
        "label": "Cinematic",
        "description": "Film-like lighting and composition",
        "steps": 32,
        "cfg_scale": 7.0,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "clip_skip": 2,
        "prompt_suffix": "cinematic lighting, dramatic atmosphere, film grain, depth of field, bokeh, movie still, anamorphic",
        "negative_prompt": (
            "low quality, worst quality, blurry, flat lighting, overexposed, "
            "amateur, snapshot, watermark, text"
        ),
    },
    "portrait": {
        "label": "Portrait",
        "description": "Close-up face shots with flattering light",
        "steps": 28,
        "cfg_scale": 6.0,
        "sampler": "dpmpp_sde",
        "scheduler": "karras",
        "clip_skip": 2,
        "width": 832,
        "height": 1216,
        "prompt_suffix": "portrait, face focus, soft natural lighting, shallow depth of field, detailed eyes, skin texture",
        "negative_prompt": (
            "low quality, worst quality, blurry, bad face, deformed eyes, "
            "asymmetric face, extra fingers, watermark"
        ),
    },
    "fashion": {
        "label": "Fashion / Editorial",
        "description": "Full-body fashion shoot aesthetic",
        "steps": 30,
        "cfg_scale": 7.0,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "clip_skip": 2,
        "width": 832,
        "height": 1216,
        "prompt_suffix": "fashion photography, editorial, studio lighting, vogue style, elegant pose, high fashion",
        "negative_prompt": (
            "low quality, worst quality, blurry, casual, messy, bad pose, "
            "watermark, text, logo"
        ),
    },
    "anime": {
        "label": "Anime",
        "description": "Clean anime/manga illustration style",
        "steps": 28,
        "cfg_scale": 7.5,
        "sampler": "euler_ancestral",
        "scheduler": "normal",
        "clip_skip": 2,
        "prompt_suffix": "masterpiece, best quality, anime style, vibrant colors, detailed, clean lineart",
        "negative_prompt": (
            "low quality, worst quality, blurry, bad anatomy, extra limbs, "
            "realistic, photo, 3d, watermark, text"
        ),
    },
    "artistic": {
        "label": "Artistic",
        "description": "Painterly, creative interpretation",
        "steps": 35,
        "cfg_scale": 8.0,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "clip_skip": 1,
        "prompt_suffix": "digital art, painterly, artistic, beautiful composition, rich colors, detailed brushwork",
        "negative_prompt": (
            "low quality, worst quality, blurry, photo, realistic, "
            "watermark, text, ugly"
        ),
    },
}

VIDEO_PRESETS: dict[str, dict[str, Any]] = {
    "subtle": {
        "label": "Subtle motion",
        "frames": 25,
        "fps": 8,
        "motion_bucket_id": 64,
        "steps": 20,
        "cfg_scale": 2.5,
    },
    "balanced": {
        "label": "Balanced",
        "frames": 25,
        "fps": 8,
        "motion_bucket_id": 127,
        "steps": 25,
        "cfg_scale": 3.0,
    },
    "dynamic": {
        "label": "Dynamic",
        "frames": 30,
        "fps": 10,
        "motion_bucket_id": 180,
        "steps": 25,
        "cfg_scale": 3.5,
    },
    "cinematic_clip": {
        "label": "Cinematic clip",
        "frames": 40,
        "fps": 12,
        "motion_bucket_id": 140,
        "steps": 30,
        "cfg_scale": 3.0,
        "width": 1024,
        "height": 576,
    },
}


def list_presets() -> list[dict[str, Any]]:
    return [
        {"id": key, **{k: v for k, v in preset.items()}}
        for key, preset in QUALITY_PRESETS.items()
    ]


def list_video_presets() -> list[dict[str, Any]]:
    return [
        {"id": key, **{k: v for k, v in preset.items()}}
        for key, preset in VIDEO_PRESETS.items()
    ]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    preset = QUALITY_PRESETS.get(preset_id) or VIDEO_PRESETS.get(preset_id) or SOCIAL_PRESETS.get(preset_id)
    if not preset:
        return None
    return {"id": preset_id, **preset}


SOCIAL_PRESETS: dict[str, dict[str, Any]] = {
    "x_post": {
        "label": "X / Twitter",
        "description": "16:9 landscape post",
        "width": 1200,
        "height": 675,
    },
    "x_square": {
        "label": "X Square",
        "description": "1:1 square post",
        "width": 1080,
        "height": 1080,
    },
    "instagram_portrait": {
        "label": "Instagram",
        "description": "4:5 portrait feed",
        "width": 1080,
        "height": 1350,
    },
    "instagram_story": {
        "label": "IG Story",
        "description": "9:16 vertical story",
        "width": 1080,
        "height": 1920,
    },
    "tiktok": {
        "label": "TikTok",
        "description": "9:16 vertical video frame",
        "width": 1080,
        "height": 1920,
    },
    "onlyfans": {
        "label": "Portrait HD",
        "description": "2:3 portrait, high detail",
        "width": 832,
        "height": 1216,
        "steps": 30,
        "cfg_scale": 6.5,
    },
}


def list_social_presets() -> list[dict[str, Any]]:
    return [{"id": key, **{k: v for k, v in preset.items()}} for key, preset in SOCIAL_PRESETS.items()]
