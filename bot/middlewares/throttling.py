"""Simple in-memory rate limiter (per-user sliding window)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger


class ThrottlingMiddleware(BaseMiddleware):
    """Drop messages when a user exceeds `limit` messages per `window` seconds."""

    def __init__(self, limit: int = 5, window: float = 5.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user is not None:
            user_id = event.from_user.id
            now = time.monotonic()
            queue = self._hits[user_id]
            while queue and now - queue[0] > self.window:
                queue.popleft()
            if len(queue) >= self.limit:
                logger.debug("Throttled user {}", user_id)
                return None
            queue.append(now)
        return await handler(event, data)
