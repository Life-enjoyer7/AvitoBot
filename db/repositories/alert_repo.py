"""CRUD operations for the AlertLog model (also used for cooldown checks)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.enums import AlertType
from db.models import AlertLog


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
