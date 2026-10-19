"""Deterministic mock listings used as a fallback when real parsing fails.

Prices oscillate slowly over time so charts and drop/rise alerts show
realistic movement during a demo, while remaining fully deterministic
(same URL -> same series of prices).
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from urllib.parse import urlparse

from db.enums import Marketplace

_TITLES: dict[Marketplace, list[str]] = {
    Marketplace.AVITO: [
        "iPhone 13 128 ГБ, идеальное состояние",
        "MacBook Air M1 2020, 8/256",
        "Велосипед горный Stels Navigator 26",
        "Sony PlayStation 5 Slim + 2 геймпада",
        "Квартира-студия 28 м², центр",
    ],
    Marketplace.YANDEX: [
        "Смартфон Samsung Galaxy A55 8/128",
        "Наушники Sony WH-1000XM5",
        "Кофемашина DeLonghi Magnifica S",
        "Ноутбук Lenovo IdeaPad 5",
        "Пылесос Dyson V15 Detect",
    ],
    Marketplace.OZON: [
        "Робот-пылесос Xiaomi Robot Vacuum",
        "Умная колонка Яндекс Станция 2",
        "Электрочайник Polaris PWK",
        "Кроссовки Nike Air Max",
        "Книга «Чистый код» Роберт Мартин",
    ],
    Marketplace.WB: [
        "Футболка хлопковая oversize",
        "Куртка демисезонная мужская",
        "Набор посуды из 10 предметов",
        "Конструктор LEGO Technic",
        "Рюкзак городской 25 л",
    ],
    Marketplace.AUTO: [
        "Lada Vesta SW Cross, 2022, 40 000 км",
        "Kia Rio X-Line, 2021, 55 000 км",
        "Toyota Camry 2.5, 2019, 90 000 км",
        "Volkswagen Tiguan, 2020, 70 000 км",
        "BMW 320i, 2018, 120 000 км",
    ],
}


def _stable_seed(value: str) -> int:
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def title_from_url(url: str) -> str | None:
    """Reconstruct a human-readable title from the URL slug, if possible.

    Used as a smarter fallback than a random mock title: even when the
    marketplace blocks the request, the link itself usually contains the
    product name (e.g. `..._nvidia_tesla_v100_32gb_..._<id>`).
    """
    parts = [p for p in urlparse(url).path.split("/") if p]
    if not parts:
        return None

    slug = parts[-1]
    # Yandex Market: /product--slug/<id>
    for part in parts:
        if "--" in part:
            slug = part.split("--", 1)[1]
            break

    # strip trailing ad/product id (6+ digits) and common noise prefixes
    slug = re.sub(r"[_-]?\d{6,}$", "", slug)
    slug = re.sub(r"^(pod_zakaz|prodazha|kuplyu|obyavlenie|zapchasti)[_-]", "", slug)

    title = " ".join(re.split(r"[_-]+", slug)).strip()
    title = " ".join(title.split())
    if len(title) < 3:
        return None
    return title[0].upper() + title[1:]


def mock_title(marketplace: Marketplace, url: str) -> str:
    from_url = title_from_url(url)
    if from_url:
        return from_url
    titles = _TITLES[marketplace]
    return titles[_stable_seed(url) % len(titles)]


def mock_price(url: str, base: float | None = None) -> float:
    """Deterministic price for a URL (base + slow +/-3% oscillation)."""
    seed = _stable_seed(url)
    if base is None:
        base = float(500 + seed % 200_000)
    bucket = int(time.time() // 600)  # 10-minute buckets
    factor = 1.0 + 0.03 * math.sin((seed % 1000) + bucket)
    return round(base * factor, 2)
