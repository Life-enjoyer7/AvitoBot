"""/start and /help handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards.reply import main_menu_kb
from db.database import async_session_factory
from db.repositories import user_repo

router = Router(name="start")

WELCOME = (
    "👋 Привет! Я <b>MarketTracker</b> — бот для отслеживания цен "
    "на Авито, Яндекс Маркете, Ozon, Wildberries и Auto.ru.\n\n"
    "Просто отправьте мне ссылку на товар, настройте условия уведомлений "
    "(падение на %, рост на %, целевая цена) — и я буду следить за ценой "
    "каждые 15 минут.\n\n"
    "Команды:\n"
    "/track — начать отслеживание\n"
    "/list — мои треки\n"
    "/history &lt;id&gt; — график цены\n"
    "/settings — настройки алертов\n"
    "/stop &lt;id&gt; — остановить трек"
)

HELP = (
    "📖 <b>Как пользоваться</b>\n\n"
    "1. Отправьте ссылку на товар (Авито, Яндекс Маркет, Ozon, WB, Auto.ru).\n"
    "2. Настройте условия: целевую цену, порог падения (%) или порог роста (%).\n"
    "3. Нажмите «Сохранить».\n\n"
    "Я проверяю цены каждые 15 минут и пришлю уведомление при срабатывании "
    "условия (но не чаще одного раза в сутки по одному условию).\n\n"
    "/list — список треков\n"
    "/history &lt;id&gt; — график истории цены\n"
    "/settings — текущие настройки\n"
    "/stop &lt;id&gt; — остановить отслеживание"
)


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
    await message.answer(WELCOME, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP, reply_markup=main_menu_kb())
