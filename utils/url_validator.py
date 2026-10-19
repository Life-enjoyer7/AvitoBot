"""URL validation and marketplace classification."""

from __future__ import annotations

from urllib.parse import urlparse

from db.enums import Marketplace

# Domain -> marketplace. Matches the exact host or any of its subdomains.
_DOMAIN_MAP: dict[str, Marketplace] = {
    "avito.ru": Marketplace.AVITO,
    "market.yandex.ru": Marketplace.YANDEX,
    "ozon.ru": Marketplace.OZON,
    "wildberries.ru": Marketplace.WB,
    "wb.ru": Marketplace.WB,
    "auto.ru": Marketplace.AUTO,
}

SUPPORTED_TEXT = (
    "Авито, Яндекс Маркет, Ozon, Wildberries, Auto.ru"
)


class UnsupportedMarketplaceError(ValueError):
    """Raised when a URL does not belong to a supported marketplace."""


def normalize_url(raw: str) -> str:
    """Return a normalized absolute URL, or raise ValueError."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("Ссылка не указана.")
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Некорректная ссылка.")
    return text


def classify_marketplace(url: str) -> Marketplace:
    """Detect the marketplace from the URL host."""
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, marketplace in _DOMAIN_MAP.items():
        if host == domain or host.endswith("." + domain):
            return marketplace
    raise UnsupportedMarketplaceError(
        f"Не поддерживаемый маркетплейс. Поддерживаются: {SUPPORTED_TEXT}."
    )
