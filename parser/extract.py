"""Shared HTML extraction helpers (JSON-LD and meta tags)."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup


def parse_price(text: str | None) -> float | None:
    """Extract a numeric price from a string like '45 990 ₽' or '45,990'. """
    if not text:
        return None
    cleaned = (
        text.replace("\u00a0", " ")
        .replace("\u2009", " ")
        .replace(" ", "")
        .replace(",", ".")
        .replace("₽", "")
        .replace("руб.", "")
        .replace("руб", "")
        .replace("BYN", "")
    )
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _find_first_key(value: Any, key: str) -> Any:
    """Return the first value associated with `key` in a nested structure."""
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for v in value.values():
            found = _find_first_key(v, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for v in value:
            found = _find_first_key(v, key)
            if found is not None:
                return found
    return None


def json_ld_image(html: str) -> str | None:
    """Return the first product image URL from JSON-LD blocks."""
    for data in _load_json_ld(html):
        image = _find_first_key(data, "image")
        if isinstance(image, str) and image.startswith("http"):
            return image
        if isinstance(image, list) and image:
            first = image[0]
            if isinstance(first, str) and first.startswith("http"):
                return first
    return None


def _load_json_ld(html: str) -> list[Any]:
    soup = BeautifulSoup(html, "lxml")
    result: list[Any] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        text = tag.string or tag.get_text()
        if not text:
            continue
        try:
            result.append(json.loads(text))
        except (json.JSONDecodeError, TypeError):
            continue
    return result


def extract_json_ld_product(html: str) -> tuple[str | None, float | None]:
    """Return (title, price) parsed from JSON-LD Product/Offer data."""
    for data in _load_json_ld(html):
        offers = _find_first_key(data, "offers")
        if offers is None:
            continue
        price: float | None = None
        if isinstance(offers, dict):
            price = parse_price(str(offers.get("price") or offers.get("lowPrice")))
        elif isinstance(offers, list) and offers and isinstance(offers[0], dict):
            first = offers[0]
            price = parse_price(str(first.get("price") or first.get("lowPrice")))

        name = _find_first_key(data, "name")
        title = name if isinstance(name, str) and name else None
        return title, price
    return None, None


def extract_meta_product(html: str) -> tuple[str | None, float | None]:
    """Return (title, price) parsed from OpenGraph / microdata meta tags."""
    soup = BeautifulSoup(html, "lxml")

    title: str | None = None
    for attr in ("property", "name"):
        tag = soup.find("meta", attrs={attr: "og:title"})
        if tag and tag.get("content"):
            title = tag["content"]
            break

    price: float | None = None
    for attr, value in (
        ("property", "product:price:amount"),
        ("itemprop", "price"),
        ("name", "price"),
    ):
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            price = parse_price(tag["content"])
            if price is not None:
                break

    if price is None:
        tag = soup.find(attrs={"itemprop": "price"})
        if tag is not None:
            price = parse_price(tag.get("content") or tag.get_text())

    return title, price
