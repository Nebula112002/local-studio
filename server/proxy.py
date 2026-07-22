"""Reverse proxy to ComfyUI for embedded web UI access."""

from __future__ import annotations

import httpx
from fastapi import Request
from starlette.responses import Response

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filtered_headers(headers: httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP or lowered in ("content-encoding", "content-length"):
            continue
        if lowered == "x-frame-options":
            continue
        out[key] = value
    return out


async def proxy_comfyui_request(base_url: str, path: str, request: Request) -> Response:
    target = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    body = await request.body()

    async with httpx.AsyncClient(timeout=900.0, follow_redirects=False) as client:
        upstream = await client.request(
            request.method,
            target,
            headers=headers,
            content=body if body else None,
        )

    if upstream.status_code in (301, 302, 303, 307, 308):
        location = upstream.headers.get("location", "")
        if location.startswith(base_url):
            location = location.replace(base_url.rstrip("/"), "/proxy/comfyui", 1)
        return Response(
            status_code=upstream.status_code,
            headers={"Location": location},
        )

    content_type = upstream.headers.get("content-type", "")
    if content_type.startswith("text/") or "javascript" in content_type or "json" in content_type:
        text = upstream.text
        base = base_url.rstrip("/")
        text = text.replace(f'"{base}/', '"/proxy/comfyui/')
        text = text.replace(f"'{base}/", "'/proxy/comfyui/")
        return Response(
            content=text,
            status_code=upstream.status_code,
            headers=_filtered_headers(upstream.headers),
            media_type=content_type.split(";")[0] or None,
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_filtered_headers(upstream.headers),
        media_type=content_type.split(";")[0] if content_type else None,
    )
