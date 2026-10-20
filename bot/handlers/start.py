"""/start and /help handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.handlers.welcome import build_welcome_text
from bot.keyboards.reply import main_menu_kb
from db.database import async_session_factory
from db.repositories import user_repo

router = Router(name="start")

HELP_TEXT = (
    "📖 <b>Как пользоваться</b>\n\n"
    "1. Отправьте ссылку на товар (Авито, Яндекс Маркет, Ozon, WB, Auto.ru).\n"
    "2. Настройте условия: целевую цену, порог падения (%) или порог роста (%).\n"
    "3. Нажмите «Сохранить».\n\n"
    "Я проверяю цены каждые 15 минут и пришлю уведомление при срабатывании "
    "условия (не чаще одного раза в сутки по одному условию).\n\n"
    "<b>Кнопки меню:</b>\n"
    "➕ Добавить товар — начать отслеживание\n"
    "📊 Мои товары — список треков\n"
    "⚙️ Настройки — условия алертов\n"
    "❓ Помощь — эта справка"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            is_premium=bool(getattr(message.from_user, "is_premium", False)),
        )
        await session.flush()
        text = await build_welcome_text(session, user.id)
        await session.commit()
    await message.answer(text, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())
