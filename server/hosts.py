"""Local Studio — bind and tailnet URL constants."""

from __future__ import annotations

import os

TAILNET_HOSTNAME = os.environ.get("LOCAL_STUDIO_TAILNET_HOSTNAME", "calebscomputer.tailfdadcb.ts.net")
PORT = int(os.environ.get("LOCAL_STUDIO_PORT", "8787"))

LOCAL_URL = f"http://127.0.0.1:{PORT}"
TAILNET_URL = f"https://{TAILNET_HOSTNAME}:{PORT}"


def service_urls() -> dict[str, str]:
    return {"local": LOCAL_URL, "tailnet": TAILNET_URL}
