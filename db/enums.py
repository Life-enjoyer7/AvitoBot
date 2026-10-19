"""Shared enums used across models and domain logic."""

from __future__ import annotations

import enum


class Marketplace(str, enum.Enum):
    """Supported marketplaces."""

    AVITO = "AVITO"
    YANDEX = "YANDEX"
    OZON = "OZON"
    WB = "WB"
    AUTO = "AUTO"


class AlertType(str, enum.Enum):
    """Types of price alerts."""

    DROP = "DROP"
    RISE = "RISE"
    TARGET = "TARGET"
    REMOVED = "REMOVED"
