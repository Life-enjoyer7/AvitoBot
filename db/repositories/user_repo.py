"""CRUD operations for the User model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_digest_users(session: AsyncSession) -> list[User]:
    """Users who enabled the daily digest."""
    result = await session.execute(
        select(User).where(User.notify_daily_digest.is_(True))
    )
    return list(result.scalars().all())


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    is_premium: bool = False,
) -> User:
    """Return the user for `telegram_id`, creating it on first contact.

    Handles the race where several concurrent requests (e.g. the Mini App
    fires /api/me, /api/tracks and /api/alerts in parallel) try to create the
    same user at once: the loser of the INSERT falls back to a fresh SELECT.

    The caller is responsible for `session.commit()`.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, username=username, is_premium=is_premium)
        session.add(user)
        try:
            await session.flush()
        except IntegrityError:
            # Another request inserted the same telegram_id first.
            await session.rollback()
            user = await get_user_by_telegram_id(session, telegram_id)
            if user is None:
                raise

    if username and user.username != username:
        user.username = username
    user.is_premium = is_premium
    return user
