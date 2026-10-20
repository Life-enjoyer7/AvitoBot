"""Inline-callback handlers (alert setup + stop buttons)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.states import TrackSetup
from bot.keyboards.inline import alert_settings_kb
from db.database import async_session_factory
from db.enums import Marketplace
from db.repositories import history_repo, track_repo, user_repo
from utils.formatting import format_price

router = Router(name="callbacks")


@router.callback_query(F.data == "set_target")
async def cb_set_target(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TrackSetup.waiting_for_target_price)
    await cb.message.edit_text("🎯 Введите целевую цену в рублях (0 — отключить):")
    await cb.answer()


@router.callback_query(F.data == "set_drop")
async def cb_set_drop(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TrackSetup.waiting_for_drop_percent)
    await cb.message.edit_text("📉 Введите порог падения в процентах (0 — отключить):")
    await cb.answer()


@router.callback_query(F.data == "set_rise")
async def cb_set_rise(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TrackSetup.waiting_for_rise_percent)
    await cb.message.edit_text("📈 Введите порог роста в процентах (0 — отключить):")
    await cb.answer()


@router.callback_query(F.data == "save_track")
async def cb_save(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("url"):
        await cb.answer("Нет данных для сохранения. Отправьте ссылку заново.", show_alert=True)
        return

    async with async_session_factory() as session:
        user = await user_repo.get_or_create_user(
            session,
            telegram_id=cb.from_user.id,
            username=cb.from_user.username,
            is_premium=bool(getattr(cb.from_user, "is_premium", False)),
        )
        await session.flush()
        track = await track_repo.create_track(
            session,
            user_id=user.id,
            marketplace=Marketplace(data["marketplace"]),
            url=data["url"],
            title=data["title"],
            current_price=data["current_price"],
            image_url=data.get("image_url"),
            alert_drop_percent=data.get("drop_percent"),
            alert_rise_percent=data.get("rise_percent"),
            target_price=data.get("target_price"),
        )
        if track.current_price is not None:
            await history_repo.add_history(session, track.id, track.current_price)
        await session.commit()

    await state.clear()
    await cb.message.edit_text(
        f"✅ Трек <b>#{track.id}</b> сохранён!\n"
        f"<b>{track.title}</b>\n"
        f"Текущая цена: <b>{format_price(track.current_price)}</b>\n\n"
        "Я буду проверять цену и пришлю уведомление при срабатывании условия."
    )
    await cb.answer("Трек сохранён")


@router.callback_query(F.data == "cancel_track")
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("❌ Настройка отменена.")
    await cb.answer()


@router.callback_query(F.data.startswith("stop:"))
async def cb_stop(cb: CallbackQuery) -> None:
    try:
        track_id = int(cb.data.split(":", 1)[1])
    except ValueError:
        await cb.answer("Некорректный id трека", show_alert=True)
        return

    async with async_session_factory() as session:
        user = await user_repo.get_or_create_user(
            session,
            telegram_id=cb.from_user.id,
            username=cb.from_user.username,
        )
        await session.flush()
        track = await track_repo.get_track(session, track_id, user_id=user.id)
        if track is None:
            await cb.answer("Трек не найден или не принадлежит вам.", show_alert=True)
            return
        await track_repo.deactivate_track(session, track)
        await session.commit()

    await cb.message.edit_text(f"⛔ Трек <b>#{track.id}</b> «{track.title}» остановлен.")
    await cb.answer("Трек остановлен")
