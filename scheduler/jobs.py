"""APScheduler background job: periodic price checks."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from core.tracker_service import build_alert_message, detect_alert, user_wants_alert
from db.database import async_session_factory
from db.enums import AlertType
from db.models import Track
from db.repositories import alert_repo, history_repo, metric_repo, track_repo, user_repo
from parser.parser_factory import ParserFactory
from utils.formatting import format_price


async def check_prices(bot: Bot) -> None:
    """Check active tracks that are due (the job ticks every 5 minutes)."""
    async with async_session_factory() as session:
        tracks = await track_repo.get_active_tracks(session)
        now = datetime.now()
        due = [t for t in tracks if _is_due(t, now)]
        logger.info("Price check: {} active, {} due", len(tracks), len(due))
        for track in due:
            try:
                await process_track(session, bot, track)
                await session.commit()
            except Exception as exc:  # noqa: BLE001 — one bad track must not kill the job
                await session.rollback()
                logger.error("Track #{} check failed: {}", track.id, exc)


def _is_due(track: Track, now: datetime) -> bool:
    """True if enough time passed since the last check (per-user interval)."""
    if track.last_checked_at is None:
        return True
    interval = getattr(track.user, "check_interval_minutes", 15) or 15
    elapsed = (now - track.last_checked_at).total_seconds()
    return elapsed >= interval * 60


async def process_track(session: AsyncSession, bot: Bot, track: Track) -> None:
    parser = ParserFactory.get_parser(track.marketplace)
    try:
        listing = await parser.parse_listing(track.url)
    except Exception as exc:  # noqa: BLE001 — parsers already swallow, this is a guard
        logger.error("Parser failed for track #{}: {}", track.id, exc)
        await metric_repo.record_event(
            session, "parse_fail", user_id=track.user_id, marketplace=track.marketplace.value
        )
        return  # skip until next cycle

    # Техническая метрика: успех = реальный HTTP с извлечённой ценой
    # (мок или «цена не найдена» — это fail).
    is_ok = (not listing.estimated) and (listing.price is not None)
    await metric_repo.record_event(
        session,
        "parse_ok" if is_ok else "parse_fail",
        user_id=track.user_id,
        marketplace=track.marketplace.value,
    )

    new_price = listing.price
    old_price = track.last_checked_price

    if new_price is None:
        await _handle_removed(session, bot, track)
        return

    # Мок/оценочные данные (парсинг заблокирован антиботом) — не перезаписываем
    # реальную цену фейковой: иначе график и алерты будут «прыгать». Просто
    # отмечаем проверку и выходим; настоящая цена обновится на следующем цикле,
    # когда парсер снова получит реальные данные.
    if listing.estimated:
        track.last_checked_at = datetime.now()
        logger.info(
            "Track #{} ({}) got estimated/mock data — keeping price {}",
            track.id, (track.title or "")[:40], track.current_price,
        )
        return

    await history_repo.add_history(session, track.id, new_price)

    alert_type = detect_alert(track, new_price)

    track.current_price = new_price
    track.last_checked_price = new_price
    track.last_checked_at = datetime.now()
    if track.image_url is None and listing.image_url:
        track.image_url = listing.image_url

    if alert_type is not None and user_wants_alert(track.user, alert_type):
        recently_sent = await alert_repo.has_recent_alert(
            session, track.id, alert_type, settings.alert_cooldown_hours
        )
        if not recently_sent:
            await alert_repo.create_alert(session, track.id, alert_type, old_price, new_price)
            await _send_alert(bot, track, alert_type, old_price, new_price)


async def _handle_removed(session: AsyncSession, bot: Bot, track: Track) -> None:
    track.is_active = False
    track.last_checked_at = datetime.now()

    recently_sent = await alert_repo.has_recent_alert(
        session, track.id, AlertType.REMOVED, settings.alert_cooldown_hours
    )
    if not recently_sent:
        await alert_repo.create_alert(
            session, track.id, AlertType.REMOVED, track.current_price, None
        )
        await _send_alert(bot, track, AlertType.REMOVED, track.current_price, None)


async def _send_alert(
    bot: Bot,
    track: Track,
    alert_type: AlertType,
    old_price: float | None,
    new_price: float | None,
) -> None:
    # Кнопка «Открыть объявление» — для CTR-метрики (кроме снятых объявлений).
    reply_markup = None
    if alert_type is not AlertType.REMOVED:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Открыть объявление",
                        callback_data=f"open:{track.id}",
                    )
                ]
            ]
        )
    try:
        await bot.send_message(
            track.user.telegram_id,
            build_alert_message(track, alert_type, old_price, new_price),
            reply_markup=reply_markup,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send {} alert for track #{}: {}", alert_type, track.id, exc)


async def send_daily_digests(bot: Bot) -> None:
    """Send a daily price summary to users who enabled it."""
    async with async_session_factory() as session:
        users = await user_repo.get_digest_users(session)
        for user in users:
            tracks = await track_repo.list_tracks(session, user.id, active_only=True)
            if not tracks:
                continue
            lines = []
            for track in tracks:
                first = await history_repo.get_first_price_since(session, track.id, days=1)
                change = ""
                if first and track.current_price:
                    chg = (track.current_price - first) / first * 100.0
                    change = ("📉" if chg < 0 else "📈") + f" {chg:+.1f}%"
                lines.append(
                    f"• <b>{track.title[:50]}</b> — {format_price(track.current_price)} {change}"
                )
            text = "📊 <b>Ежедневная сводка</b>\n\n" + "\n".join(lines)
            try:
                await bot.send_message(user.telegram_id, text)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to send daily digest to {}: {}", user.telegram_id, exc)
        await session.commit()
