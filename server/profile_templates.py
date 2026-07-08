"""Starter character templates for quick setup."""

from __future__ import annotations

from typing import Any

PROFILE_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "fitness_model",
        "name": "Athletic Fitness",
        "hair": "long dark brown ponytail",
        "eyes": "hazel",
        "skin_tone": "tan",
        "body_type": "athletic toned physique",
        "age_range": "mid 20s",
        "ethnicity": "Latina",
        "distinctive_features": "defined abs, confident smile",
        "art_style": "photorealistic",
        "default_outfit": "sports bra and leggings",
        "personality_vibe": "energetic, confident",
        "prompt_prefix": "masterpiece, best quality, highly detailed, fitness photography",
        "negative_prompt": (
            "low quality, worst quality, blurry, deformed, bad anatomy, "
            "extra limbs, watermark, text, logo, overweight"
        ),
        "preferred_width": 832,
        "preferred_height": 1216,
        "preferred_steps": 30,
        "preferred_cfg": 6.5,
        "scene_ideas": [
            "gym mirror selfie, morning light",
            "outdoor park workout, golden hour",
            "yoga studio, soft natural lighting",
            "beach running, sunset backdrop",
            "rooftop city view, athletic pose",
        ],
        "tags": ["fitness", "athletic", "lifestyle"],
    },
    {
        "template_id": "glamour_editorial",
        "name": "Glamour Editorial",
        "hair": "long platinum blonde waves",
        "eyes": "ice blue",
        "skin_tone": "fair porcelain",
        "body_type": "slim elegant figure",
        "age_range": "mid 20s",
        "ethnicity": "European",
        "distinctive_features": "high cheekbones, glossy lips",
        "art_style": "fashion photography",
        "default_outfit": "designer evening gown",
        "personality_vibe": "elegant, mysterious",
        "prompt_prefix": "masterpiece, best quality, vogue editorial, studio lighting, 8k uhd",
        "negative_prompt": (
            "low quality, worst quality, blurry, deformed, bad anatomy, "
            "watermark, text, casual, messy"
        ),
        "preferred_width": 832,
        "preferred_height": 1216,
        "preferred_steps": 32,
        "preferred_cfg": 7.0,
        "scene_ideas": [
            "luxury hotel suite, window light",
            "neon city street at night, cinematic",
            "marble staircase, dramatic lighting",
            "champagne bar, warm ambient glow",
            "black studio backdrop, high fashion pose",
        ],
        "tags": ["glamour", "fashion", "editorial"],
    },
    {
        "template_id": "girl_next_door",
        "name": "Girl Next Door",
        "hair": "medium length auburn",
        "eyes": "warm green",
        "skin_tone": "light with freckles",
        "body_type": "natural curvy figure",
        "age_range": "early 20s",
        "ethnicity": "Caucasian",
        "distinctive_features": "freckles across nose, warm smile, dimples",
        "art_style": "photorealistic",
        "default_outfit": "casual sundress",
        "personality_vibe": "sweet, approachable, playful",
        "prompt_prefix": "masterpiece, best quality, natural beauty, soft lighting, candid photo",
        "negative_prompt": (
            "low quality, worst quality, blurry, deformed, bad anatomy, "
            "watermark, text, overly edited, plastic"
        ),
        "preferred_width": 1024,
        "preferred_height": 1024,
        "preferred_steps": 28,
        "preferred_cfg": 6.0,
        "scene_ideas": [
            "cozy coffee shop, morning window light",
            "sunflower field, golden hour",
            "bedroom with fairy lights, soft glow",
            "farmers market, candid laugh",
            "rainy window, cozy sweater, warm mood",
        ],
        "tags": ["natural", "cute", "lifestyle"],
    },
]


def list_templates() -> list[dict[str, Any]]:
    return [{"template_id": t["template_id"], "name": t["name"], "tags": t.get("tags", [])} for t in PROFILE_TEMPLATES]


def get_template(template_id: str) -> dict[str, Any] | None:
    for t in PROFILE_TEMPLATES:
        if t["template_id"] == template_id:
            return {k: v for k, v in t.items() if k != "template_id"}
    return None
