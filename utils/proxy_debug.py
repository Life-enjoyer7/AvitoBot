"""Helpers to inspect the parser proxy configuration at runtime."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx


def mask_proxy(url: str | None) -> str:
    """Return the proxy URL with the password hidden (safe for logs)."""
    if not url:
        return "<empty>"
    try:
        p = urlparse(url)
        host = p.hostname or "?"
        port = f":{p.port}" if p.port else ""
        user = f"{p.username}@" if p.username else ""
        return f"{p.scheme}://{user}{host}{port}"
    except Exception:  # noqa: BLE001
        return "<invalid proxy url>"


async def probe_proxy(url: str | None, timeout: float = 15.0) -> dict:
    """Fetch ipinfo through the proxy to verify it works.

    Returns {"ok": True, "ip": ..., "country": ..., "city": ...} or
    {"ok": False, "error": "..."}.
    """
    if not url:
        return {"ok": False, "error": "PARSER_PROXY_URL is empty"}
    try:
        async with httpx.AsyncClient(proxy=url, timeout=timeout) as client:
            resp = await client.get("https://ipinfo.io/json")
            data = resp.json()
            return {
                "ok": True,
                "ip": data.get("ip"),
                "country": data.get("country"),
                "city": data.get("city"),
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
