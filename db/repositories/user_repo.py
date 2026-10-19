"""CRUD operations for the User model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    is_premium: bool = False,
) -> User:
    """Return the user for `telegram_id`, creating it on first contact.

    The caller is responsible for `session.commit()`.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, username=username, is_premium=is_premium)
        session.add(user)
        await session.flush()
    else:
        if username and user.username != username:
            user.username = username
        user.is_premium = is_premium
    return user
