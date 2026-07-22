from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# App lives on D:\AI; generation outputs go to G: (slower drive is fine for writes).
DEFAULT_OUTPUT_DIR_WIN = Path(r"G:\Generation\Local-Studio\output")


def agent_output_dir() -> Path:
    env = os.environ.get("LOCAL_STUDIO_OUTPUT_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        return DEFAULT_OUTPUT_DIR_WIN
    local = ROOT_DIR / "output"
    return local
