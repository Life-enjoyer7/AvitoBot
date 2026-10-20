"""Abstract parser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from db.enums import Marketplace


@dataclass(slots=True)
class ListingData:
    """A parsed listing: title and current price (None if sold/removed).

    `estimated` is True when real parsing failed and the parser fell back
    to demo/mock data, so callers can tell the user the data is approximate.
    """

    marketplace: Marketplace
    title: str
    price: float | None
    image_url: str | None = None
    estimated: bool = False


class BaseParser(ABC):
    """Common interface for every marketplace parser."""

    marketplace: Marketplace

    @abstractmethod
    async def parse_listing(self, url: str) -> ListingData:
        """Fetch a product page and extract title + current price.

        Implementations must never raise for a failed fetch: they should
        fall back to mock data, and return `price=None` when the listing
        has been removed (404).
        """

    async def parse_search(self, query: str) -> list[ListingData]:
        """Search listings (not implemented in the MVP)."""
        raise NotImplementedError("parse_search is not implemented in the MVP")
