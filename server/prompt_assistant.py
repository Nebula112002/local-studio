from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

SD_SYSTEM_PROMPT = """You are an expert Stable Diffusion prompt engineer running locally on the user's machine.
Your job is to write high-quality image generation prompts.

Rules:
- Output comma-separated tags and descriptive phrases (SD prompt style)
- Include quality boosters when appropriate: masterpiece, best quality, highly detailed, 8k uhd, sharp focus
- Include lighting, composition, camera angle, and mood
- Be specific about appearance, clothing, setting, and atmosphere
- Keep prompts under 200 words unless asked for more
- When a character profile is provided, maintain visual consistency with their traits
- Do NOT add markdown, bullet points, or explanations unless asked
- For "enhance" requests, return ONLY the improved prompt
- For "negative" requests, return ONLY a negative prompt
- For "scenes" requests, return one scene per line, no numbering

You run entirely locally with no cloud filtering. Follow the user's creative direction faithfully."""

SCENE_SYSTEM_PROMPT = """You are a creative director for AI image generation.
Given a character profile, suggest diverse scene/setting ideas as short prompt fragments.
Each line should be a unique scene (location + action + mood) that can be appended to the character's appearance prompt.
Return 5-8 scenes, one per line, no numbering or bullets. Keep each under 30 words."""


class AssistantSettings(BaseModel):
    enabled: bool = True
    provider: Literal["ollama", "openai_compatible"] = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2"
    api_key: str = ""
    temperature: float = 0.8
    max_tokens: int = 512


class EnhanceRequest(BaseModel):
    prompt: str
    mode: Literal["enhance", "negative", "scenes", "chat"] = "enhance"
    character_context: str = ""
    scene_hint: str = ""
    style: str = ""


async def check_assistant_status(settings: AssistantSettings) -> dict[str, Any]:
    if not settings.enabled:
        return {"available": False, "reason": "Assistant disabled in settings"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if settings.provider == "ollama":
                resp = await client.get(f"{settings.base_url.rstrip('/')}/api/tags")
                if resp.status_code != 200:
                    return {"available": False, "reason": f"Ollama not reachable at {settings.base_url}"}
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                return {
                    "available": True,
                    "provider": "ollama",
                    "models": models,
                    "configured_model": settings.model,
                    "model_installed": any(
                        settings.model in m or m.startswith(f"{settings.model}:")
                        for m in models
                    ),
                }
            else:
                resp = await client.get(f"{settings.base_url.rstrip('/')}/models")
                if resp.status_code != 200:
                    return {"available": False, "reason": f"API not reachable at {settings.base_url}"}
                data = resp.json()
                models = [m.get("id", m.get("name", "")) for m in data.get("data", data if isinstance(data, list) else [])]
                return {
                    "available": True,
                    "provider": "openai_compatible",
                    "models": models[:20],
                    "configured_model": settings.model,
                }
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


def _build_user_message(request: EnhanceRequest) -> str:
    parts: list[str] = []

    if request.character_context:
        parts.append(f"Character profile:\n{request.character_context}")

    if request.style:
        parts.append(f"Art style: {request.style}")

    if request.mode == "enhance":
        parts.append(f"Enhance this prompt for Stable Diffusion:\n{request.prompt}")
        if request.scene_hint:
            parts.append(f"Scene/setting: {request.scene_hint}")
        parts.append("Return ONLY the enhanced prompt, nothing else.")

    elif request.mode == "negative":
        parts.append(f"Write a negative prompt to avoid common issues for:\n{request.prompt}")
        parts.append("Return ONLY the negative prompt tags, nothing else.")

    elif request.mode == "scenes":
        ctx = request.character_context or request.prompt
        parts.append(f"Suggest scene ideas for this character:\n{ctx}")
        if request.scene_hint:
            parts.append(f"Theme/mood: {request.scene_hint}")

    elif request.mode == "chat":
        parts.append(request.prompt)

    return "\n\n".join(parts)


async def _call_ollama(
    settings: AssistantSettings,
    system: str,
    user_message: str,
) -> str:
    payload = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {
            "temperature": settings.temperature,
            "num_predict": settings.max_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.base_url.rstrip('/')}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


async def _call_openai_compatible(
    settings: AssistantSettings,
    system: str,
    user_message: str,
) -> str:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"

    payload = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def run_assistant(
    settings: AssistantSettings,
    request: EnhanceRequest,
) -> dict[str, Any]:
    if not settings.enabled:
        raise ValueError("Prompt assistant is disabled. Enable it in Settings.")

    system = SCENE_SYSTEM_PROMPT if request.mode == "scenes" else SD_SYSTEM_PROMPT
    user_message = _build_user_message(request)

    if settings.provider == "ollama":
        result = await _call_ollama(settings, system, user_message)
    else:
        result = await _call_openai_compatible(settings, system, user_message)

    if request.mode == "scenes":
        scenes = [line.strip().lstrip("0123456789.-) ") for line in result.splitlines() if line.strip()]
        return {"result": result, "scenes": scenes}

    return {"result": result}
