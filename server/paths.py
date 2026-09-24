from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# App lives on D:\AI; generation outputs go to G: (slower drive is fine for writes).
# Same shared library Stability Matrix shows. ComfyUI's output folder junctions here.
DEFAULT_OUTPUT_DIR_WIN = Path(r"G:\Generation\StabilityMatrix-win-x64\Data\Images")


def agent_output_dir() -> Path:
    env = os.environ.get("LOCAL_STUDIO_OUTPUT_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        return DEFAULT_OUTPUT_DIR_WIN
    local = ROOT_DIR / "output"
    return local


def resolve_output_file(filename: str) -> Path:
    """Resolve a gallery path inside the shared output folder. Rejects escapes."""
    root = agent_output_dir().resolve()
    rel = Path(str(filename).replace("\\", "/"))
    if rel.is_absolute() or any(part in ("..", "") for part in rel.parts):
        raise ValueError("Invalid filename")
    path = (root / rel).resolve()
    path.relative_to(root)
    return path
