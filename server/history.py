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
    scheduler: str = "normal",
    clip_skip: int = 1,
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
        "scheduler": scheduler,
        "clip_skip": clip_skip,
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


def _output_files():
    out = _output_dir()
    media = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".gif"}
    files = []
    for path in out.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in media:
            continue
        rel = path.relative_to(out)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(path)
    return files


def _find_output_file(name: str) -> Path | None:
    out = _output_dir().resolve()
    rel = Path(str(name).replace("\\", "/"))
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        return None
    direct = (out / rel).resolve()
    try:
        direct.relative_to(out)
    except ValueError:
        return None
    if direct.is_file():
        return direct
    base = rel.name
    for path in _output_files():
        if path.name == base:
            return path.resolve()
    return None


def _delete_entry_files(entry: dict[str, Any]) -> list[str]:
    deleted_files: list[str] = []
    for name in entry.get("files") or []:
        candidate = _find_output_file(str(name))
        if candidate is None or not candidate.is_file():
            continue
        rel = candidate.relative_to(_output_dir().resolve()).as_posix()
        candidate.unlink()
        deleted_files.append(rel)
    return deleted_files


def _unlink_output(path: Path, deleted_files: list[str]) -> None:
    out = _output_dir().resolve()
    try:
        rel = path.resolve().relative_to(out).as_posix()
    except ValueError:
        return
    if rel in deleted_files or not path.is_file():
        return
    path.unlink()
    deleted_files.append(rel)


def _delete_files_since(cutoff: float | None, deleted_files: list[str]) -> None:
    """Remove library media in the window. cutoff None removes every listed file."""
    for path in _output_files():
        if cutoff is not None and path.stat().st_mtime < cutoff:
            continue
        _unlink_output(path, deleted_files)


def delete_history_bulk(*, within_hours: float | None = None, clear_all: bool = False) -> dict[str, Any]:
    """Delete history entries and the library files in that same window.

    within_hours: remove entries and media from the last N hours.
    clear_all: wipe the history index and every media file Studio lists.
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
        _delete_files_since(None, deleted_files)
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

    _delete_files_since(cutoff, deleted_files)
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
    files = _output_files()
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        if path.name == HISTORY_INDEX or path.suffix.lower() == ".json":
            continue
        rel = path.relative_to(out).as_posix()
        kind = "video" if path.suffix.lower() in (".mp4", ".webm", ".gif") else "image"
        items.append({
            "filename": rel,
            "media_type": kind,
            "size": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
        if len(items) >= 200:
            break
    return items
