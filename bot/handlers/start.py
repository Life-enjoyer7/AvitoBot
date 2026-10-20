"""/start and /help handlers.

The bot itself is now only a notification service: it sends price alerts.
All product management (add/list/edit/delete) lives in the Mini App.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from config.settings import settings
from db.database import async_session_factory
from db.repositories import user_repo

router = Router(name="start")

START_TEXT = (
    "🛒 <b>MarketTracker</b>\n\n"
    "Я слежу за ценами на ваши товары и присылаю уведомления, когда цена "
    "падает, растёт или достигает цели.\n\n"
    "Управление товарами — в приложении:"
)

HELP_TEXT = (
    "📖 <b>MarketTracker</b>\n\n"
    "Бот присылает уведомления об изменении цен. Добавление, настройка "
    "условий и удаление товаров — в приложении.\n\n"
    "Откройте приложение через кнопку меню (☰) или кнопку ниже."
)


def _app_keyboard() -> InlineKeyboardMarkup | None:
    if settings.webapp_url:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🌐 Открыть приложение",
                        web_app=WebAppInfo(url=settings.webapp_url),
                    )
                ]
            ]
        )
    return None


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session_factory() as session:
        await user_repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            is_premium=bool(getattr(message.from_user, "is_premium", False)),
        )
        await session.commit()
    await message.answer(START_TEXT, reply_markup=_app_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=_app_keyboard())
