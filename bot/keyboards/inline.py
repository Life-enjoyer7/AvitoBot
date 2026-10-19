"""Inline keyboards."""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import Track
from utils.formatting import format_percent, format_price


def alert_settings_kb(data: dict[str, Any]) -> InlineKeyboardMarkup:
    """Keyboard for configuring alert rules, reflecting the current values."""
    target = data.get("target_price")
    drop = data.get("drop_percent")
    rise = data.get("rise_percent")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🎯 Целевая цена: {format_price(target)}",
            callback_data="set_target",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"📉 Падение: {format_percent(drop)}",
            callback_data="set_drop",
        ),
        InlineKeyboardButton(
            text=f"📈 Рост: {format_percent(rise)}",
            callback_data="set_rise",
        ),
    )
    builder.row(
        InlineKeyboardButton(text="✅ Сохранить", callback_data="save_track"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_track"),
    )
    return builder.as_markup()


def tracks_list_kb(tracks: list[Track]) -> InlineKeyboardMarkup:
    """Keyboard with a stop button for each active track."""
    builder = InlineKeyboardBuilder()
    for track in tracks:
        if track.is_active:
            builder.row(
                InlineKeyboardButton(
                    text=f"⛔ Остановить #{track.id}",
                    callback_data=f"stop:{track.id}",
                )
            )
    return builder.as_markup()
