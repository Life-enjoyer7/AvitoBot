"""Avito parser.

Data sources, tried in order (never raises):
  1. Mobile API  — m.avito.ru/api/1/card/items/{id}. Returns real JSON card
     data (title, price, image). Requires a browser-like TLS fingerprint
     (Avito blocks httpx/aiohttp), so it uses curl_cffi with
     `impersonate="chrome"`. Requests are throttled and rate-limit errors
     are retried with backoff.
  2. HTML page   — JSON-LD / OpenGraph / microdata (fallback).
  3. Mock data   — deterministic demo data as a last resort.
"""

from __future__ import annotations

import asyncio
import random
import re
import time
from urllib.parse import urlparse

from loguru import logger

from db.enums import Marketplace
from parser import extract, mock_data
from parser.base_parser import BaseParser, ListingData
from parser.http import get_cffi_session, get_http_client

# --- Global rate limiter for the Avito mobile API ------------------------
_MIN_INTERVAL = 5.0  # seconds between mobile-API requests
_RATE_LIMIT_BACKOFF = 20.0  # seconds to wait after a 403/429 before retrying
_last_request_at = 0.0
_throttle_lock = asyncio.Lock()


async def _throttle() -> None:
    """Ensure a minimum interval (+ jitter) between Avito mobile-API requests."""
    global _last_request_at
    async with _throttle_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        # Small random jitter makes the request pattern less bot-like.
        await asyncio.sleep(random.uniform(0.5, 1.5))
        _last_request_at = time.monotonic()


def _get_path(obj, *keys):
    """Safely navigate a nested dict: _get_path(d, "a", "b", "c")."""
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


class AvitoParser(BaseParser):
    marketplace = Marketplace.AVITO

    _ITEM_API_URL = "https://m.avito.ru/api/1/card/items/{item_id}"
    _MOBILE_HEADERS = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru-RU,ru;q=0.9",
        "referer": "https://m.avito.ru/",
        "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Mobile Safari/537.36"
        ),
    }

    async def parse_listing(self, url: str) -> ListingData:
        item_id = self._extract_item_id(url)
        if item_id:
            title, price, image = await self._fetch_mobile_api(item_id)
            if title:
                logger.info("Avito card {} fetched via mobile API", item_id)
                return ListingData(
                    marketplace=self.marketplace,
                    title=title,
                    price=price,
                    image_url=image,
                )
            # Mobile API failed (blocked / rate-limited / removed). The HTML
            # page is blocked even harder by Avito, so don't fire a second
            # request that only deepens the rate limit — fall back to mock.
            return self._mock(url)

        # No numeric item id in the URL — HTML is the only option left.
        return await self._parse_html(url)

    async def _fetch_mobile_api(
        self, item_id: str
    ) -> tuple[str | None, float | None, str | None]:
        session = get_cffi_session()
        url = self._ITEM_API_URL.format(item_id=item_id)

        for attempt in range(3):
            await _throttle()
            try:
                response = await session.get(url, headers=self._MOBILE_HEADERS, timeout=25)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Avito mobile API error (attempt {}/3): {}", attempt + 1, exc
                )
                await asyncio.sleep(5)
                continue

            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Avito mobile API bad JSON: {}", exc)
                    return None, None, None
                mobile = _get_path(data, "success", "mobile") or {}
                if isinstance(mobile, dict):
                    title = mobile.get("title")
                    if title:
                        return title, self._extract_price(mobile), self._extract_image(mobile)
                return None, None, None

            # 403 — IP blocked; 429 — rate limit; 439 — Avito anti-bot ("too
            # many / suspicious requests"). All are worth a backoff-and-retry.
            if response.status_code in (403, 429, 439):
                logger.warning(
                    "Avito blocked/limited ({}) attempt {}/3, waiting {}s",
                    response.status_code, attempt + 1, _RATE_LIMIT_BACKOFF,
                )
                await asyncio.sleep(_RATE_LIMIT_BACKOFF)
                continue

            return None, None, None

        return None, None, None

    @staticmethod
    def _extract_price(mobile: dict) -> float | None:
        price_node = mobile.get("price")
        if not isinstance(price_node, dict):
            return None
        raw = price_node.get("value") or price_node.get("value_signed")
        price = extract.parse_price(str(raw)) if raw else None
        if price is None:
            text = _get_path(
                price_node, "current", "attributes", "price", "value", "title"
            )
            price = extract.parse_price(str(text)) if text else None
        return price

    @staticmethod
    def _extract_image(mobile: dict) -> str | None:
        images = mobile.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                for key in ("url", "uri", "orig", "640x480", "480x360", "src"):
                    value = first.get(key)
                    if isinstance(value, str) and value.startswith("http"):
                        return value
                for value in first.values():
                    if isinstance(value, str) and value.startswith("http"):
                        return value
            elif isinstance(first, str) and first.startswith("http"):
                return first
        return None

    async def _parse_html(self, url: str) -> ListingData:
        client = get_http_client()
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.info("Avito listing removed (404): {}", url)
                return ListingData(marketplace=self.marketplace, title="", price=None)
            response.raise_for_status()
            return self._extract(response.text, url)
        except Exception as exc:  # noqa: BLE001 — parser must never crash the bot
            logger.warning("Avito HTML parse failed for {}: {} — falling back to mock", url, exc)
            return self._mock(url)

    def _extract(self, html: str, url: str) -> ListingData:
        title, price = extract.extract_json_ld_product(html)
        if title is None or price is None:
            m_title, m_price = extract.extract_meta_product(html)
            title = title or m_title
            price = price if price is not None else m_price
        title = title or mock_data.mock_title(self.marketplace, url)
        return ListingData(
            marketplace=self.marketplace,
            title=title,
            price=price,
            image_url=extract.json_ld_image(html),
        )

    def _mock(self, url: str) -> ListingData:
        return ListingData(
            marketplace=self.marketplace,
            title=mock_data.mock_title(self.marketplace, url),
            price=mock_data.mock_price(url),
            estimated=True,
        )

    @staticmethod
    def _extract_item_id(url: str) -> str | None:
        """Extract the trailing Avito item id from the URL path."""
        path = urlparse(url).path.rstrip("/")
        match = re.search(r"(\d{6,})$", path)
        return match.group(1) if match else None
