"""Shared HTTP clients for all parsers.

- httpx.AsyncClient — generic requests (supports `PARSER_PROXY_URL`).
- curl_cffi AsyncSession (impersonate="chrome") — browser-TLS requests for
  marketplaces that block plain HTTP clients (Avito, Yandex Market).
"""

from __future__ import annotations

import httpx
from curl_cffi.requests import AsyncSession

from config.settings import settings

_client: httpx.AsyncClient | None = None
_cffi_session: AsyncSession | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the lazily-created shared httpx AsyncClient."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            proxy=settings.parser_proxy_url,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
    return _client


async def close_http_client() -> None:
    """Close the shared httpx client (call on shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def get_cffi_session() -> AsyncSession:
    """Return a shared curl_cffi session impersonating Chrome (lazy).

    Honors `PARSER_PROXY_URL` so marketplace requests (Avito/Yandex) can be
    routed through a residential proxy when the host IP is blocked.
    """
    global _cffi_session
    if _cffi_session is None:
        proxies = None
        if settings.parser_proxy_url:
            proxies = {
                "http": settings.parser_proxy_url,
                "https": settings.parser_proxy_url,
            }
        _cffi_session = AsyncSession(impersonate="chrome", proxies=proxies)
    return _cffi_session


async def close_cffi_session() -> None:
    """Close the shared curl_cffi session (call on shutdown)."""
    global _cffi_session
    if _cffi_session is not None:
        try:
            await _cffi_session.close()
        except Exception:  # noqa: BLE001
            pass
        _cffi_session = None
