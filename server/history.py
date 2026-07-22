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


def delete_history_item(item_id: str) -> dict[str, Any] | None:
    """Remove a history entry and delete its files from disk."""
    index = _load_index()
    entry: dict[str, Any] | None = None
    filtered: list[dict[str, Any]] = []
    for item in index:
        if item.get("id") == item_id:
            entry = item
        else:
            filtered.append(item)
    if entry is None:
        return None

    deleted_files = _delete_entry_files(entry)
    _save_index(filtered)
    return {
        "id": item_id,
        "deleted_files": deleted_files,
        "files_removed": len(deleted_files),
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _delete_entry_files(entry: dict[str, Any]) -> list[str]:
    out = _output_dir().resolve()
    deleted_files: list[str] = []
    for name in entry.get("files") or []:
        candidate = (out / Path(str(name)).name).resolve()
        try:
            candidate.relative_to(out)
        except ValueError:
            continue
        if candidate.is_file():
            candidate.unlink()
            deleted_files.append(candidate.name)
    return deleted_files


def delete_history_bulk(*, within_hours: float | None = None, clear_all: bool = False) -> dict[str, Any]:
    """Delete history entries (and their files).

    within_hours: remove entries created in the last N hours.
    clear_all: wipe the full history index and all media in the output folder.
    """
    if not clear_all and within_hours is None:
        raise ValueError("Provide within_hours or clear_all")
    if within_hours is not None and within_hours <= 0:
        raise ValueError("within_hours must be positive")

    index = _load_index()
    now = datetime.now(timezone.utc)
    keep: list[dict[str, Any]] = []
    removed_entries = 0
    deleted_files: list[str] = []

    if clear_all:
        for entry in index:
            deleted_files.extend(_delete_entry_files(entry))
            removed_entries += 1
        # Also wipe orphan media left in the output folder.
        out = _output_dir()
        for path in out.iterdir():
            if not path.is_file():
                continue
            if path.name == HISTORY_INDEX or path.suffix.lower() == ".json":
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm"}:
                try:
                    path.unlink()
                    if path.name not in deleted_files:
                        deleted_files.append(path.name)
                except OSError:
                    pass
        _save_index([])
        return {
            "removed_entries": removed_entries,
            "files_removed": len(deleted_files),
            "deleted_files": deleted_files,
            "clear_all": True,
        }

    cutoff = now.timestamp() - (within_hours * 3600)
    for entry in index:
        ts = _parse_timestamp(entry.get("timestamp"))
        # If timestamp is missing/unparseable, treat as recent so bulk clear still catches it.
        entry_ts = ts.timestamp() if ts else now.timestamp()
        if entry_ts >= cutoff:
            deleted_files.extend(_delete_entry_files(entry))
            removed_entries += 1
        else:
            keep.append(entry)

    _save_index(keep)
    return {
        "removed_entries": removed_entries,
        "files_removed": len(deleted_files),
        "deleted_files": deleted_files,
        "within_hours": within_hours,
        "remaining": len(keep),
    }


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
