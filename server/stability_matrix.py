"""Stability Matrix install detection and ComfyUI status probing."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class StabilityMatrixPaths:
    exe: str | None
    data_dir: str | None
    comfyui_package: str | None
    models_dir: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "exe": self.exe,
            "data_dir": self.data_dir,
            "comfyui_package": self.comfyui_package,
            "models_dir": self.models_dir,
        }


def find_stability_matrix_exe(configured: str | None = None) -> str | None:
    if configured and configured.strip():
        path = Path(configured.strip())
        if path.is_file():
            return str(path.resolve())
        exe = path / "StabilityMatrix.exe"
        if exe.is_file():
            return str(exe.resolve())

    env_path = os.environ.get("STABILITY_MATRIX_PATH", "").strip()
    if env_path:
        found = find_stability_matrix_exe(env_path)
        if found:
            return found

    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        ROOT_DIR.parent / "StabilityMatrix-win-x64" / "StabilityMatrix.exe",
        ROOT_DIR.parent / "StabilityMatrix" / "StabilityMatrix.exe",
        Path("G:/Generation/StabilityMatrix-win-x64/StabilityMatrix.exe"),
        Path("C:/StabilityMatrix/StabilityMatrix.exe"),
        Path("D:/StabilityMatrix/StabilityMatrix.exe"),
        Path(local_app) / "StabilityMatrix/StabilityMatrix.exe",
        Path.home() / "StabilityMatrix/StabilityMatrix.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def resolve_stability_matrix_paths(configured: str | None = None) -> StabilityMatrixPaths:
    exe = find_stability_matrix_exe(configured)
    if not exe:
        return StabilityMatrixPaths(None, None, None, None)

    root = Path(exe).parent
    data_dir = root / "Data"
    if not data_dir.is_dir():
        data_dir = root

    comfyui = data_dir / "Packages" / "ComfyUI"
    models = data_dir / "Models"
    return StabilityMatrixPaths(
        exe=exe,
        data_dir=str(data_dir.resolve()) if data_dir.is_dir() else None,
        comfyui_package=str(comfyui.resolve()) if comfyui.is_dir() else None,
        models_dir=str(models.resolve()) if models.is_dir() else None,
    )


def _host_port(comfyui_url: str) -> tuple[str, int]:
    parsed = urlparse(comfyui_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 8188)
    return host, port


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def probe_comfyui(comfyui_url: str) -> dict[str, Any]:
    """Return ComfyUI reachability and user-facing guidance."""
    host, port = _host_port(comfyui_url)
    port_open = _port_open(host, port)

    if not port_open:
        return {
            "status": "offline",
            "connected": False,
            "port_open": False,
            "url": comfyui_url.rstrip("/"),
            "message": (
                f"ComfyUI is not reachable at {comfyui_url}. "
                "Launch ComfyUI once from Stability Matrix → Packages → ComfyUI → Launch."
            ),
            "hint": (
                "If you already started ComfyUI elsewhere, confirm Settings → ComfyUI URL "
                f"matches that instance (default http://127.0.0.1:8188)."
            ),
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{comfyui_url.rstrip('/')}/system_stats")
            if response.status_code == 200:
                return {
                    "status": "ready",
                    "connected": True,
                    "port_open": True,
                    "url": comfyui_url.rstrip("/"),
                    "message": (
                        f"ComfyUI is already running on port {port}. "
                        "Use this instance — do not launch a second ComfyUI from Stability Matrix."
                    ),
                    "hint": (
                        "If Stability Matrix shows a Launch error about port 8188 or database lock, "
                        "ComfyUI is already running. Open Image Lab in Stability Matrix or use the "
                        "embed below instead of clicking Launch again."
                    ),
                }
    except Exception:
        pass

    return {
        "status": "port_busy",
        "connected": False,
        "port_open": True,
        "url": comfyui_url.rstrip("/"),
        "message": (
            f"Port {port} is in use but ComfyUI did not respond at {comfyui_url}. "
            "Another process may be bound to this port, or ComfyUI may still be starting."
        ),
        "hint": (
            "Wait a few seconds and click Reload. If the problem persists, stop the process "
            f"using port {port} or change ComfyUI URL in Settings."
        ),
    }
