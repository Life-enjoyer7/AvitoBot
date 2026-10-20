"""Telegram client session factory (IPv4-first, optional proxy).

Why: on some networks api.telegram.org is unreachable because the IPv6 stack
is broken (TLS handshake resets) or the ISP throttles Telegram. Forcing IPv4
and allowing a proxy covers both cases.
"""

from __future__ import annotations

import socket

from aiogram.client.session.aiohttp import AiohttpSession

from config.settings import settings


class _IPv4AiohttpSession(AiohttpSession):
    """Force IPv4 to survive networks with a broken IPv6 stack."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if self.proxy is None:
            self._connector_init["family"] = socket.AF_INET


def create_bot_session() -> AiohttpSession:
    """Build the Telegram session: IPv4-only, optionally through a proxy."""
    if settings.telegram_proxy_url:
        try:
            return _IPv4AiohttpSession(proxy=settings.telegram_proxy_url)
        except RuntimeError as exc:
            raise RuntimeError(
                "Для TELEGRAM_PROXY_URL установите aiohttp-socks: "
                "pip install aiohttp-socks"
            ) from exc
    return _IPv4AiohttpSession()
