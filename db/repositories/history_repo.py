"""CRUD operations for the PriceHistory model."""

from __future__ import annotations

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
