"""Reply-keyboard button handlers (main menu)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from bot.handlers.commands import show_list, show_settings
from bot.handlers.start import HELP_TEXT
from bot.handlers.track import TRACK_PROMPT
from bot.keyboards.reply import (
    BTN_ADD,
    BTN_HELP,
    BTN_LIST,
    BTN_SETTINGS,
    main_menu_kb,
)

router = Router(name="menu")


@router.message(F.text == BTN_ADD)
async def btn_add(message: Message) -> None:
    await message.answer(TRACK_PROMPT, reply_markup=main_menu_kb())


@router.message(F.text == BTN_LIST)
async def btn_list(message: Message) -> None:
    await show_list(message)


@router.message(F.text == BTN_SETTINGS)
async def btn_settings(message: Message) -> None:
    await show_settings(message)


@router.message(F.text == BTN_HELP)
async def btn_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())
