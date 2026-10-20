"""Link handling and the alert-setup dialog (FSM)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.states import TrackSetup
from bot.keyboards.inline import alert_settings_kb
from bot.keyboards.reply import main_menu_kb
from parser.parser_factory import ParserFactory
from utils.formatting import format_price
from utils.url_validator import (
    UnsupportedMarketplaceError,
    classify_marketplace,
    normalize_url,
)

router = Router(name="track")

TRACK_PROMPT = (
    "Отправьте ссылку на товар с поддерживаемого маркетплейса.\n\n"
    "Поддерживаются: Авито, Яндекс Маркет, Ozon, Wildberries, Auto.ru"
)

_NUMBER_RE = r"^\d+([.,]\d+)?$"


def _parse_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


@router.message(Command("track"))
async def cmd_track(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(TRACK_PROMPT, reply_markup=main_menu_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Настройка отменена.")


@router.message(~F.text.startswith("/"), F.text.regexp(r"https?://\S+"))
async def on_url(message: Message, state: FSMContext) -> None:
    raw = message.text or ""
    try:
        url = normalize_url(raw)
        marketplace = classify_marketplace(url)
    except (ValueError, UnsupportedMarketplaceError) as exc:
        await message.answer(f"⚠️ {exc}")
        return

    status = await message.answer("⏳ Анализирую товар...")
    try:
        listing = await ParserFactory.get_parser(marketplace).parse_listing(url)
    except Exception:  # noqa: BLE001 — last-resort guard, parsers already swallow errors
        await status.edit_text("❌ Не удалось обработать ссылку, попробуйте позже.")
        return

    if listing.price is None:
        await status.edit_text("⚠️ Не удалось определить цену (возможно, объявление удалено).")
        return

    await state.clear()
    await state.set_state(TrackSetup.configuring)
    data = {
        "url": url,
        "marketplace": marketplace.value,
        "title": listing.title or "Без названия",
        "current_price": listing.price,
        "target_price": None,
        "drop_percent": 5.0,
        "rise_percent": None,
    }
    await state.update_data(**data)

    note = ""
    if listing.estimated:
        note = (
            "\n⚠️ Маркетплейс ограничил доступ (403/антибот), поэтому показаны "
            "демо-данные: название взято из ссылки, цена — примерная.\n"
        )

    await status.edit_text(
        f"<b>{data['title']}</b>\n"
        f"🏪 {data['marketplace']}\n"
        f"💰 Текущая цена: <b>{format_price(data['current_price'])}</b>\n"
        f"{note}\n"
        "Настройте условия уведомлений:",
        reply_markup=alert_settings_kb(data),
    )


@router.message(TrackSetup.waiting_for_target_price, F.text.regexp(_NUMBER_RE))
async def on_target_price(message: Message, state: FSMContext) -> None:
    value = _parse_float(message.text)
    if value is None or value < 0:
        await message.answer("Введите цену числом, например 50000 (0 — отключить).")
        return
    data = await state.get_data()
    data["target_price"] = value if value > 0 else None
    await state.set_data(data)
    await state.set_state(TrackSetup.configuring)
    await message.answer("✅ Целевая цена обновлена.", reply_markup=alert_settings_kb(data))


@router.message(TrackSetup.waiting_for_drop_percent, F.text.regexp(_NUMBER_RE))
async def on_drop_percent(message: Message, state: FSMContext) -> None:
    value = _parse_float(message.text)
    if value is None or value > 100:
        await message.answer("Введите процент от 0 до 100 (0 — отключить).")
        return
    data = await state.get_data()
    data["drop_percent"] = value if value > 0 else None
    await state.set_data(data)
    await state.set_state(TrackSetup.configuring)
    await message.answer("✅ Порог падения обновлён.", reply_markup=alert_settings_kb(data))


@router.message(TrackSetup.waiting_for_rise_percent, F.text.regexp(_NUMBER_RE))
async def on_rise_percent(message: Message, state: FSMContext) -> None:
    value = _parse_float(message.text)
    if value is None or value > 100:
        await message.answer("Введите процент от 0 до 100 (0 — отключить).")
        return
    data = await state.get_data()
    data["rise_percent"] = value if value > 0 else None
    await state.set_data(data)
    await state.set_state(TrackSetup.configuring)
    await message.answer("✅ Порог роста обновлён.", reply_markup=alert_settings_kb(data))


# Fallbacks: re-prompt on invalid input while waiting for a value.
@router.message(TrackSetup.waiting_for_target_price)
async def on_target_price_invalid(message: Message) -> None:
    await message.answer("Введите целевую цену числом (например, 50000) или /cancel.")


@router.message(TrackSetup.waiting_for_drop_percent)
async def on_drop_percent_invalid(message: Message) -> None:
    await message.answer("Введите порог падения в процентах (например, 5) или /cancel.")


@router.message(TrackSetup.waiting_for_rise_percent)
async def on_rise_percent_invalid(message: Message) -> None:
    await message.answer("Введите порог роста в процентах (например, 10) или /cancel.")


@router.message(TrackSetup.configuring, F.text)
async def on_configuring_stray(message: Message) -> None:
    await message.answer("Используйте кнопки под сообщением или /cancel для отмены.")
