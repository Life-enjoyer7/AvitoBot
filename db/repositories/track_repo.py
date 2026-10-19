"""CRUD operations for the Track model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.enums import Marketplace
from db.models import Track


async def create_track(
    session: AsyncSession,
    *,
    user_id: int,
    marketplace: Marketplace,
    url: str,
    title: str,
    current_price: float | None,
    alert_drop_percent: float | None = 5.0,
    alert_rise_percent: float | None = None,
    target_price: float | None = None,
) -> Track:
    """Create a track. The caller is responsible for `session.commit()`."""
    track = Track(
        user_id=user_id,
        marketplace=marketplace,
        url=url,
        title=title,
        current_price=current_price,
        last_checked_price=current_price,
        alert_drop_percent=alert_drop_percent,
        alert_rise_percent=alert_rise_percent,
        target_price=target_price,
        last_checked_at=datetime.now() if current_price is not None else None,
    )
    session.add(track)
    await session.flush()
    return track


async def get_track(
    session: AsyncSession, track_id: int, user_id: int | None = None
) -> Track | None:
    stmt = select(Track).where(Track.id == track_id)
    if user_id is not None:
        stmt = stmt.where(Track.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_tracks(
    session: AsyncSession, user_id: int, active_only: bool = False
) -> list[Track]:
    stmt = select(Track).where(Track.user_id == user_id).order_by(Track.id)
    if active_only:
        stmt = stmt.where(Track.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_tracks(session: AsyncSession) -> list[Track]:
    """All active tracks with their owner eagerly loaded (for notifications)."""
    stmt = (
        select(Track)
        .where(Track.is_active.is_(True))
        .options(selectinload(Track.user))
        .order_by(Track.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def deactivate_track(session: AsyncSession, track: Track) -> Track:
    track.is_active = False
    session.add(track)
    await session.flush()
    return track
