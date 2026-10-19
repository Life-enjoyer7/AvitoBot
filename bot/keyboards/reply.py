"""Reply keyboards."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Main menu shown after /start."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="/track"),
        KeyboardButton(text="/list"),
        KeyboardButton(text="/help"),
    )
    builder.adjust(3)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
