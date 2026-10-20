"""APScheduler background job: periodic price checks."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from core.tracker_service import build_alert_message, detect_alert
from db.database import async_session_factory
from db.enums import AlertType
from db.models import Track
from db.repositories import alert_repo, history_repo, track_repo
from parser.parser_factory import ParserFactory


async def check_prices(bot: Bot) -> None:
    """Check every active track once (runs on the APScheduler interval)."""
    async with async_session_factory() as session:
        tracks = await track_repo.get_active_tracks(session)
        logger.info("Price check started for {} track(s)", len(tracks))
        for track in tracks:
            try:
                await process_track(session, bot, track)
                await session.commit()
            except Exception as exc:  # noqa: BLE001 — one bad track must not kill the job
                await session.rollback()
                logger.error("Track #{} check failed: {}", track.id, exc)


async def process_track(session: AsyncSession, bot: Bot, track: Track) -> None:
    parser = ParserFactory.get_parser(track.marketplace)
    try:
        listing = await parser.parse_listing(track.url)
    except Exception as exc:  # noqa: BLE001 — parsers already swallow, this is a guard
        logger.error("Parser failed for track #{}: {}", track.id, exc)
        return  # skip until next cycle

    new_price = listing.price
    old_price = track.last_checked_price

    if new_price is None:
        await _handle_removed(session, bot, track)
        return

    await history_repo.add_history(session, track.id, new_price)

    alert_type = detect_alert(track, new_price)

    track.current_price = new_price
    track.last_checked_price = new_price
    track.last_checked_at = datetime.now()
    if track.image_url is None and listing.image_url:
        track.image_url = listing.image_url

    if alert_type is not None:
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
    try:
        await bot.send_message(
            track.user.telegram_id,
            build_alert_message(track, alert_type, old_price, new_price),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send {} alert for track #{}: {}", alert_type, track.id, exc)
