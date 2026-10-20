"""MarketTracker — entry point.

Wires together: logging, database, Telegram bot + dispatcher, routers,
middlewares, and the APScheduler background price-check job.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from bot.handlers import callbacks, commands, menu, start, track
from bot.middlewares.errors import register_error_handlers
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.session import create_bot_session
from config.settings import settings
from db.database import dispose_db, init_db
from parser.http import close_cffi_session, close_http_client
from scheduler.jobs import check_prices
from utils.logger import setup_logger


async def main() -> None:
    """Application entry point."""
    setup_logger()

    if not settings.bot_token:
        logger.error(
            "BOT_TOKEN is not set. Copy `.env.example` to `.env` "
            "and set your token from @BotFather."
        )
        raise SystemExit(1)

    await init_db()
    logger.info("Database initialized.")

    bot = Bot(
        token=settings.bot_token,
        session=create_bot_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(ThrottlingMiddleware())
    register_error_handlers(dp)

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(track.router)
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        check_prices,
        trigger="interval",
        minutes=settings.scheduler_interval_minutes,
        args=[bot],
        id="check_prices",
        name="Price check",
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started (every {} min).", settings.scheduler_interval_minutes)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await close_cffi_session()
        await close_http_client()
        await dispose_db()
        await bot.session.close()
        logger.info("MarketTracker stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MarketTracker interrupted by user.")
