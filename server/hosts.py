"""Local Studio — bind and public URL constants.

Demand proxy binds the app on LOCAL_STUDIO_PORT (often 18787) while the
stable public face stays on 8787 (proxy + Tailscale serve + warehouse edge).
"""

from __future__ import annotations

import os

TAILNET_HOSTNAME = os.environ.get("LOCAL_STUDIO_TAILNET_HOSTNAME", "calebscomputer.tailfdadcb.ts.net")

# Bind port (backend). Watchdog sets this to 18787 behind the demand proxy.
BIND_PORT = int(os.environ.get("LOCAL_STUDIO_PORT", "8787"))

# Public face — never change these; phone/tailnet/edge all expect 8787.
PUBLIC_PORT = int(os.environ.get("LOCAL_STUDIO_PUBLIC_PORT", "8787"))

# Back-compat alias used by older callers.
PORT = PUBLIC_PORT

LOCAL_URL = f"http://127.0.0.1:{PUBLIC_PORT}"
TAILNET_URL = f"https://{TAILNET_HOSTNAME}:{PUBLIC_PORT}"


def service_urls() -> dict[str, str]:
    return {
        "local": LOCAL_URL,
        "tailnet": TAILNET_URL,
        "bind_port": str(BIND_PORT),
        "public_port": str(PUBLIC_PORT),
    }
