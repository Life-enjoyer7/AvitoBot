"""Stub parsers for marketplaces not implemented in the MVP.

They always return deterministic mock data so the bot remains fully
functional end-to-end; real parsing can be added later without changing
the public interface.
"""

from __future__ import annotations

from loguru import logger

from db.enums import Marketplace
from parser import mock_data
from parser.base_parser import BaseParser, ListingData


class _StubBase(BaseParser):
    async def parse_listing(self, url: str) -> ListingData:
        logger.info("Stub parser used for {}", self.marketplace.value)
        return ListingData(
            marketplace=self.marketplace,
            title=mock_data.mock_title(self.marketplace, url),
            price=mock_data.mock_price(url),
            estimated=True,
        )


class OzonParser(_StubBase):
    marketplace = Marketplace.OZON


class WildberriesParser(_StubBase):
    marketplace = Marketplace.WB


class AutoParser(_StubBase):
    marketplace = Marketplace.AUTO
