"""Yandex Market parser.

Uses curl_cffi (browser TLS fingerprint) — plain httpx only gets an empty
JS shell page from Yandex. Data is extracted from JSON-LD / OpenGraph, with
deterministic mock data as a fallback so the parser never raises.
"""

from __future__ import annotations

from loguru import logger

from db.enums import Marketplace
from parser import extract, mock_data
from parser.base_parser import BaseParser, ListingData
from parser.http import get_cffi_session


class YandexParser(BaseParser):
    marketplace = Marketplace.YANDEX

    async def parse_listing(self, url: str) -> ListingData:
        session = get_cffi_session()
        try:
            response = await session.get(url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Yandex fetch failed for {}: {} — falling back to mock", url, exc)
            return self._mock(url)

        if response.status_code == 404:
            logger.info("Yandex product removed (404): {}", url)
            return ListingData(marketplace=self.marketplace, title="", price=None)

        if response.status_code != 200:
            logger.warning("Yandex HTTP {}: {}", response.status_code, url)
            return self._mock(url)

        title, price = extract.extract_json_ld_product(response.text)
        if title is None or price is None:
            m_title, m_price = extract.extract_meta_product(response.text)
            title = title or m_title
            price = price if price is not None else m_price

        if title and price is not None:
            return ListingData(marketplace=self.marketplace, title=title, price=price)

        return self._mock(url)

    def _mock(self, url: str) -> ListingData:
        return ListingData(
            marketplace=self.marketplace,
            title=mock_data.mock_title(self.marketplace, url),
            price=mock_data.mock_price(url),
            estimated=True,
        )
