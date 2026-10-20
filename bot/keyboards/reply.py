"""Reply keyboards."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BTN_ADD = "➕ Добавить товар"
BTN_LIST = "📊 Мои товары"
BTN_SETTINGS = "⚙️ Настройки"
BTN_HELP = "❓ Помощь"


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Main menu shown after /start and kept across the dialog."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=BTN_ADD),
        KeyboardButton(text=BTN_LIST),
        KeyboardButton(text=BTN_SETTINGS),
    )
    builder.row(KeyboardButton(text=BTN_HELP))
    builder.adjust(3, 1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
