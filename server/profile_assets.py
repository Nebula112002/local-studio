from __future__ import annotations

import base64
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "profile_assets"


def _profile_dir(profile_id: str) -> Path:
    d = ASSETS_DIR / profile_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_reference(profile_id: str, image_b64: str) -> str:
    path = _profile_dir(profile_id) / "reference.png"
    path.write_bytes(base64.b64decode(image_b64))
    return str(path.relative_to(ROOT_DIR))


def get_reference_b64(profile_id: str) -> str | None:
    path = _profile_dir(profile_id) / "reference.png"
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")


def has_reference(profile_id: str) -> bool:
    return (_profile_dir(profile_id) / "reference.png").exists()


def save_thumbnail(profile_id: str, image_b64: str) -> str:
    path = _profile_dir(profile_id) / "thumbnail.png"
    path.write_bytes(base64.b64decode(image_b64))
    return str(path.relative_to(ROOT_DIR))


def get_thumbnail_b64(profile_id: str) -> str | None:
    path = _profile_dir(profile_id) / "thumbnail.png"
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")


def delete_assets(profile_id: str) -> None:
    path = ASSETS_DIR / profile_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
