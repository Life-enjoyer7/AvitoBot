"""Commands: /list, /stop, /history, /settings.

The list/settings logic is shared with the reply-keyboard buttons in
`bot/handlers/menu.py`.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from bot.keyboards.inline import tracks_list_kb
from core.history_service import build_price_chart
from db.database import async_session_factory
from db.repositories import history_repo, track_repo, user_repo
from utils.formatting import format_percent, format_price

router = Router(name="commands")


async def _get_user_id(session, message: Message) -> int:
    user = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
    await session.flush()
    return user.id


async def show_list(message: Message) -> None:
    """Shared logic for /list and the «Мои товары» button."""
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, message)
        tracks = await track_repo.list_tracks(session, user_id)
        await session.commit()

    if not tracks:
        await message.answer(
            "У вас пока нет треков. Отправьте ссылку на товар или нажмите "
            "«➕ Добавить товар»."
        )
        return

    lines = []
    for t in tracks:
        status = "✅" if t.is_active else "⛔"
        lines.append(
            f"{status} <b>#{t.id}</b> — {t.title}\n"
            f"🏪 {t.marketplace.value} · 💰 {format_price(t.current_price)}\n"
            f"🎯 {format_price(t.target_price)} · 📉 {format_percent(t.alert_drop_percent)}"
            f" · 📈 {format_percent(t.alert_rise_percent)}"
        )
    await message.answer(
        "📋 <b>Ваши треки:</b>\n\n" + "\n\n".join(lines),
        reply_markup=tracks_list_kb(tracks),
    )


async def show_settings(message: Message) -> None:
    """Shared logic for /settings and the «Настройки» button."""
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, message)
        tracks = await track_repo.list_tracks(session, user_id)
        await session.commit()

    if not tracks:
        await message.answer("Нет сохранённых настроек. Отправьте ссылку на товар.")
        return

    lines = []
    for t in tracks:
        lines.append(
            f"<b>#{t.id}</b> {t.title}\n"
            f"🎯 целевая: {format_price(t.target_price)}\n"
            f"📉 падение: {format_percent(t.alert_drop_percent)}\n"
            f"📈 рост: {format_percent(t.alert_rise_percent)}\n"
            f"состояние: {'активен' if t.is_active else 'остановлен'}"
        )
    await message.answer("⚙️ <b>Настройки треков:</b>\n\n" + "\n\n".join(lines))


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    await show_list(message)


@router.message(Command("stop"))
async def cmd_stop(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Использование: /stop &lt;track_id&gt; (id — в /list).")
        return

    async with async_session_factory() as session:
        user_id = await _get_user_id(session, message)
        track = await track_repo.get_track(session, int(arg), user_id=user_id)
        if track is None:
            await message.answer("Трек не найден или не принадлежит вам.")
            return
        await track_repo.deactivate_track(session, track)
        await session.commit()

    await message.answer(f"⛔ Трек <b>#{track.id}</b> «{track.title}» остановлен.")


@router.message(Command("history"))
async def cmd_history(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Использование: /history &lt;track_id&gt; (id — в /list).")
        return

    async with async_session_factory() as session:
        user_id = await _get_user_id(session, message)
        track = await track_repo.get_track(session, int(arg), user_id=user_id)
        if track is None:
            await message.answer("Трек не найден или не принадлежит вам.")
            return
        history = await history_repo.get_history(session, track.id, limit=14)
        await session.commit()

    if len(history) < 2:
        await message.answer(
            "Для графика нужно минимум 2 замера. Подождите следующий цикл проверки."
        )
        return

    image = build_price_chart(history, track.title)
    await message.answer_photo(
        BufferedInputFile(image.getvalue(), filename="chart.png"),
        caption=f"📈 <b>#{track.id}</b> — {track.title}",
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    await show_settings(message)
