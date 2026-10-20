"""CRUD operations for the PriceHistory model."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PriceHistory


async def add_history(
    session: AsyncSession, track_id: int, price: float
) -> PriceHistory:
    entry = PriceHistory(track_id=track_id, price=price)
    session.add(entry)
    await session.flush()
    return entry


async def get_history(
    session: AsyncSession, track_id: int, limit: int = 14
) -> list[PriceHistory]:
    """Return the most recent `limit` observations in chronological order."""
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.track_id == track_id)
        .order_by(PriceHistory.timestamp.desc(), PriceHistory.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(reversed(result.scalars().all()))


async def get_history_since(
    session: AsyncSession, track_id: int, days: int
) -> list[PriceHistory]:
    """Return all observations within the last `days` days, chronological."""
    since = datetime.now() - timedelta(days=days)
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.track_id == track_id, PriceHistory.timestamp >= since)
        .order_by(PriceHistory.timestamp.asc(), PriceHistory.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_first_price_since(
    session: AsyncSession, track_id: int, days: int = 7
) -> float | None:
    """Return the oldest price recorded within the last `days` days."""
    since = datetime.now() - timedelta(days=days)
    stmt = (
        select(PriceHistory.price)
        .where(PriceHistory.track_id == track_id, PriceHistory.timestamp >= since)
        .order_by(PriceHistory.timestamp.asc(), PriceHistory.id.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
