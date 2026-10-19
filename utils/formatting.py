"""Small shared formatting helpers."""

from __future__ import annotations


def format_price(value: float | None) -> str:
    """Format a price as '12 345 ₽' (or '—' when unknown)."""
    if value is None:
        return "—"
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def format_percent(value: float | None) -> str:
    """Format a percent threshold as '5%' (or 'выкл' when disabled)."""
    if value is None:
        return "выкл"
    return f"{value:g}%"
