"""MarketTracker — entry point.

Wires together: logging, database, Telegram bot + dispatcher, routers,
middlewares, the APScheduler price-check job, and the FastAPI Mini App.
"""

from __future__ import annotations

import asyncio
import os

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from bot.handlers import start
from bot.middlewares.errors import register_error_handlers
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.session import create_bot_session
from config.settings import settings
from db.database import dispose_db, init_db
from parser.http import close_cffi_session, close_http_client
from scheduler.jobs import check_prices, send_daily_digests
from utils.logger import setup_logger
from utils.proxy_debug import mask_proxy, probe_proxy
from web.api import app as web_app


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

    # --- Парсер-прокси: показать конфиг и проверить доступность ---
    logger.info("Parser proxy: {}", mask_proxy(settings.parser_proxy_url))
    proxy_info = await probe_proxy(settings.parser_proxy_url)
    if proxy_info.get("ok"):
        logger.info(
            "Proxy check OK: egress IP {} ({}, {})",
            proxy_info.get("ip"),
            proxy_info.get("city"),
            proxy_info.get("country"),
        )
    else:
        logger.warning("Proxy check FAILED: {}", proxy_info.get("error"))

    bot = Bot(
        token=settings.bot_token,
        session=create_bot_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    if settings.webapp_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть приложение",
                    web_app=WebAppInfo(url=settings.webapp_url),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось установить кнопку меню: {}", exc)

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(ThrottlingMiddleware())
    register_error_handlers(dp)

    dp.include_router(start.router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        check_prices,
        trigger="interval",
        minutes=5,  # минимальный «тик»; фактическая проверка — по частоте пользователя
        args=[bot],
        id="check_prices",
        name="Price check",
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        send_daily_digests,
        trigger=CronTrigger(hour=9, minute=0, timezone="Europe/Moscow"),
        args=[bot],
        id="daily_digest",
        name="Daily digest",
        coalesce=True,
        max_instances=1,
    )
    if settings.keep_alive and settings.webapp_url:
        import httpx

        async def _keep_alive_ping() -> None:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.get(f"{settings.webapp_url}/healthz")
            except Exception as exc:  # noqa: BLE001
                logger.debug("keep-alive ping failed: {}", exc)

        scheduler.add_job(
            _keep_alive_ping,
            trigger="interval",
            minutes=5,
            id="keep_alive",
            name="Keep-alive ping",
            coalesce=True,
            max_instances=1,
        )
        logger.info("Keep-alive enabled (ping {}/healthz every 5 min).", settings.webapp_url)

    scheduler.start()
    logger.info("Scheduler started (tick every 5 min).")

    web_port = int(os.environ.get("PORT", settings.webapp_port))
    web_server = uvicorn.Server(
        uvicorn.Config(
            web_app,
            host=settings.webapp_host,
            port=web_port,
            log_level="warning",
        )
    )
    web_task = asyncio.create_task(web_server.serve())
    logger.info("Mini App served at http://{}:{}", settings.webapp_host, settings.webapp_port)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        web_server.should_exit = True
        await web_task
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
