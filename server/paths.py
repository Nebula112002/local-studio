from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def agent_output_dir() -> Path:
    env = os.environ.get("LOCAL_STUDIO_OUTPUT_DIR")
    if env:
        return Path(env)
    local = ROOT_DIR / "output"
    if local.exists():
        return local
    if os.name == "nt":
        return Path(r"D:\AI\sites\local-studio\output")
    return local