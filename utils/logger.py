"""Loguru configuration.

Provides `setup_logger()` which removes the default sink and adds:
  * a colorized console sink at `settings.log_level`;
  * a rotating file sink (with retention + compression) in `settings.log_dir`.
"""

from __future__ import annotations

import sys

from loguru import logger

from config.settings import settings

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{name}:{function}:{line} | {message}"
)


def setup_logger() -> None:
    """(Re)configure loguru sinks. Safe to call multiple times."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=_CONSOLE_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=settings.log_level.upper() == "DEBUG",
    )

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        settings.log_dir / "market_tracker_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format=_FILE_FORMAT,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        encoding="utf-8",
        enqueue=True,  # non-blocking, thread-safe writes
    )

    logger.debug("Logging configured: console + rotated file sink.")
