"""/start and /help handlers.

The bot itself is now only a notification service: it sends price alerts.
All product management (add/list/edit/delete) lives in the Mini App.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from db.database import async_session_factory
from db.repositories import metric_repo, track_repo, user_repo

router = Router(name="start")

START_TEXT = (
    "🛒 <b>MarketTracker</b>\n\n"
    "Я слежу за ценами на ваши товары и присылаю уведомления, когда цена "
    "падает, растёт или достигает цели.\n\n"
    "Управление товарами — в приложении: нажмите кнопку меню (☰) и "
    "«Открыть приложение»."
)

HELP_TEXT = (
    "📖 <b>MarketTracker</b>\n\n"
    "Бот присылает уведомления об изменении цен. Добавление, настройка "
    "условий и удаление товаров — в приложении.\n\n"
    "Откройте приложение через кнопку меню (☰) → «Открыть приложение»."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await metric_repo.record_event(session, "start", user_id=user.id)
        await session.commit()
    # ReplyKeyboardRemove снимает залипшую клавиатуру от старых версий бота.
    await message.answer(START_TEXT, reply_markup=ReplyKeyboardRemove())


@router.callback_query(F.data.startswith("open:"))
async def on_open_link(callback: CallbackQuery) -> None:
    """Inline "Открыть объявление" in an alert — track the click (CTR)."""
    try:
        track_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return

    url = None
    async with async_session_factory() as session:
        track = await track_repo.get_track(session, track_id)
        if track is not None:
            url = track.url
            await metric_repo.record_event(
                session,
                "alert_click",
                user_id=track.user_id,
                track_id=track_id,
                marketplace=track.marketplace.value,
            )
            await session.commit()

    if url:
        await callback.answer(url=url)
    else:
        await callback.answer("Объявление недоступно")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
