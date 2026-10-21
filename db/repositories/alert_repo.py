"""CRUD operations for the AlertLog model (also used for cooldown checks)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.enums import AlertType
from db.models import AlertLog, Track


async def create_alert(
    session: AsyncSession,
    track_id: int,
    alert_type: AlertType,
    old_price: float | None = None,
    new_price: float | None = None,
) -> AlertLog:
    entry = AlertLog(
        track_id=track_id,
        alert_type=alert_type,
        old_price=old_price,
        new_price=new_price,
    )
    session.add(entry)
    await session.flush()
    return entry


async def has_recent_alert(
    session: AsyncSession,
    track_id: int,
    alert_type: AlertType,
    cooldown_hours: int,
) -> bool:
    """True if an alert of this type was already sent within the cooldown."""
    since = datetime.now() - timedelta(hours=cooldown_hours)
    stmt = (
        select(AlertLog.id)
        .where(
            AlertLog.track_id == track_id,
            AlertLog.alert_type == alert_type,
            AlertLog.sent_at >= since,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def count_alerts_for_user(session: AsyncSession, user_id: int) -> int:
    stmt = (
        select(func.count(AlertLog.id))
        .join(Track, AlertLog.track_id == Track.id)
        .where(Track.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one() or 0


async def count_unread_alerts(session: AsyncSession, user_id: int) -> int:
    stmt = (
        select(func.count(AlertLog.id))
        .join(Track, AlertLog.track_id == Track.id)
        .where(Track.user_id == user_id, AlertLog.is_read.is_(False))
    )
    result = await session.execute(stmt)
    return result.scalar_one() or 0


async def delete_all_alerts(session: AsyncSession, user_id: int) -> None:
    """Delete all of the user's alerts (the "clear notifications" button)."""
    from sqlalchemy import delete

    stmt = delete(AlertLog).where(
        AlertLog.track_id.in_(
            select(Track.id).where(Track.user_id == user_id)
        )
    )
    await session.execute(stmt)


async def list_alerts_for_user(
    session: AsyncSession, user_id: int, limit: int = 30
) -> list[tuple[AlertLog, str]]:
    """Return (alert, track_title) pairs for a user, newest first."""
    stmt = (
        select(AlertLog, Track.title)
        .join(Track, AlertLog.track_id == Track.id)
        .where(Track.user_id == user_id)
        .order_by(AlertLog.sent_at.desc(), AlertLog.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.all())
