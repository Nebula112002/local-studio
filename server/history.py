from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.paths import agent_output_dir

HISTORY_INDEX = "history.json"
MAX_HISTORY = 500


def _output_dir() -> Path:
    d = agent_output_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return _output_dir() / HISTORY_INDEX


def _load_index() -> list[dict[str, Any]]:
    path = _index_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_index(entries: list[dict[str, Any]]) -> None:
    trimmed = entries[:MAX_HISTORY]
    _index_path().write_text(json.dumps(trimmed, indent=2), encoding="utf-8")


def record_generation(
    *,
    mode: str,
    prompt: str,
    negative_prompt: str,
    seeds: list[int],
    width: int,
    height: int,
    steps: int,
    cfg_scale: float,
    sampler: str,
    model: str | None,
    files: list[str],
    media_type: str = "image",
    profile_id: str | None = None,
    profile_name: str | None = None,
) -> dict[str, Any]:
    entry = {
        "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{seeds[0] if seeds else 0}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seeds": seeds,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler": sampler,
        "model": model,
        "files": files,
        "media_type": media_type,
        "profile_id": profile_id,
        "profile_name": profile_name,
    }
    index = _load_index()
    index.insert(0, entry)
    _save_index(index)
    return entry


def list_history(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    index = _load_index()
    return {
        "total": len(index),
        "items": index[offset : offset + limit],
    }


def get_history_item(item_id: str) -> dict[str, Any] | None:
    for entry in _load_index():
        if entry.get("id") == item_id:
            return entry
    return None


def delete_history_item(item_id: str) -> bool:
    index = _load_index()
    filtered = [e for e in index if e.get("id") != item_id]
    if len(filtered) == len(index):
        return False
    _save_index(filtered)
    return True


def scan_output_files() -> list[dict[str, Any]]:
    """List files in output directory for gallery restore."""
    out = _output_dir()
    items: list[dict[str, Any]] = []
    for path in sorted(out.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name == HISTORY_INDEX or path.suffix == ".json":
            continue
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            items.append({
                "filename": path.name,
                "path": str(path),
                "media_type": "image",
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        elif path.suffix.lower() in (".mp4", ".webm", ".gif"):
            items.append({
                "filename": path.name,
                "path": str(path),
                "media_type": "video",
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
    return items[:200]
