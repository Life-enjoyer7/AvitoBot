"""Global error handling (registered via Dispatcher.errors)."""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.types import ErrorEvent
from loguru import logger


def register_error_handlers(dp: Dispatcher) -> None:
    @dp.errors()
    async def on_unhandled_error(event: ErrorEvent) -> None:
        logger.exception("Unhandled error", exc_info=event.exception)
